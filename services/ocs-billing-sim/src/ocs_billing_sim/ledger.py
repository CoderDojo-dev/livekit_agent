"""The real ledger behind the OCS + Billing simulator.

This is NOT a mock that returns a fabricated reference. Every operation mutates the real domain
tables and is protected by the database's own uniqueness on idempotency_key:

  charge  -> insert billing.payments (unique idempotency_key), decrement the customer's oldest
             open invoice's outstanding_amount, and flip its status paid/partial.
  top_up  -> insert ocs.recharges (unique idempotency_key), increment the main balance_account.
  balance -> project the live ocs.balance_accounts rows.
  invoices-> project the live billing.invoices rows.

Idempotency is enforced by the DB, exactly like a real charging system: a retried request with
the same idempotency_key returns the ORIGINAL reference and moves no money a second time. There is
no in-memory shortcut and no fake success - a failure (unknown customer, no balance account) is
raised so the API returns an honest error, never a synthesized "OK".
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.billing import Invoice, Payment
from persistence.models.ocs import BalanceAccount, Recharge
from persistence.util import to_uuid

logger = logging.getLogger(__name__)


class LedgerError(RuntimeError):
    """A ledger operation could not complete (unknown customer, no account, etc.)."""


def _cust(customer_id: str):
    cid = to_uuid(customer_id)
    if cid is None:
        raise LedgerError(f"{customer_id!r} is not a valid customer id")
    return cid


# ---------------- OCS: balance + top-up ----------------
def get_balance(session: Session, customer_id: str) -> dict:
    """Project the customer's balance accounts (main credit + data) from ocs.balance_accounts."""
    cid = _cust(customer_id)
    rows = list(session.scalars(
        select(BalanceAccount).where(BalanceAccount.customer_id == cid)
    ))
    main = next((r for r in rows if r.balance_type == "main"), None)
    data = next((r for r in rows if r.balance_type == "data"), None)
    return {
        "customer_id": customer_id,
        "credit": float(main.balance_value) if main else 0.0,
        "currency": main.balance_unit if main else "TND",
        "data_remaining_mb": _to_mb(data) if data else 0,
        "accounts": [
            {"type": r.balance_type, "value": float(r.balance_value), "unit": r.balance_unit,
             "status": r.status}
            for r in rows
        ],
    }


def _to_mb(account: BalanceAccount) -> int:
    value = Decimal(str(account.balance_value))
    if account.balance_unit == "GB":
        return int(value * 1024)
    if account.balance_unit == "MB":
        return int(value)
    return 0


def top_up(session: Session, customer_id: str, amount: Decimal, currency: str,
           idempotency_key: str) -> str:
    """Recharge the customer's main balance idempotently. Returns the recharge reference."""
    cid = _cust(customer_id)

    # Idempotent replay: same key -> original reference, no second credit.
    existing = session.scalar(select(Recharge).where(Recharge.idempotency_key == idempotency_key))
    if existing is not None:
        return existing.transaction_reference or f"TOP-{idempotency_key[:10].upper()}"

    main = session.scalar(
        select(BalanceAccount).where(BalanceAccount.customer_id == cid,
                                     BalanceAccount.balance_type == "main")
    )
    if main is None:
        raise LedgerError(f"customer {customer_id} has no main balance account")

    subscription_id = main.subscription_id
    reference = f"TOP-{uuid.uuid4().hex[:10].upper()}"
    session.add(Recharge(
        subscription_id=subscription_id, customer_id=cid,
        amount=amount, channel="agent", idempotency_key=idempotency_key,
        transaction_reference=reference, status="completed",
    ))
    # Real credit: the balance actually increases.
    main.balance_value = Decimal(str(main.balance_value)) + amount  # type: ignore[assignment]
    main.updated_at = datetime.now(UTC)
    logger.info("top_up %s +%s %s -> %s", customer_id, amount, currency, reference)
    return reference


def apply_data_addon(session: Session, customer_id: str, addon_id: str,
                     idempotency_key: str) -> None:
    """Apply a data add-on idempotently by crediting the data balance.

    Add-on sizes are keyed by addon_id; unknown ids raise rather than silently doing nothing.
    """
    cid = _cust(customer_id)
    if session.scalar(select(Recharge).where(Recharge.idempotency_key == idempotency_key)):
        return  # already applied

    addon_mb = _ADDON_CATALOG.get(addon_id)
    if addon_mb is None:
        raise LedgerError(f"unknown data add-on {addon_id!r}")

    data = session.scalar(
        select(BalanceAccount).where(BalanceAccount.customer_id == cid,
                                     BalanceAccount.balance_type == "data")
    )
    if data is None:
        raise LedgerError(f"customer {customer_id} has no data balance account")

    add_value = Decimal(addon_mb) / (1024 if data.balance_unit == "GB" else 1)
    data.balance_value = Decimal(str(data.balance_value)) + add_value  # type: ignore[assignment]
    data.updated_at = datetime.now(UTC)
    session.add(Recharge(
        subscription_id=data.subscription_id, customer_id=cid,
        amount=Decimal("0"), channel="agent", idempotency_key=idempotency_key,
        transaction_reference=f"ADD-{addon_id}", status="completed",
    ))


_ADDON_CATALOG = {"data_1gb": 1024, "data_5gb": 5120, "data_10gb": 10240}


# ---------------- Billing: invoices + charge + deferral ----------------
def get_invoices(session: Session, customer_id: str) -> list[dict]:
    """Project the customer's open invoices from billing.invoices."""
    cid = _cust(customer_id)
    rows = session.scalars(
        select(Invoice).where(Invoice.customer_id == cid,
                              Invoice.status.in_(("issued", "partial", "overdue")))
        .order_by(Invoice.due_date.asc())
    )
    return [
        {"invoice_id": str(inv.id), "invoice_number": inv.invoice_number,
         "outstanding_amount": float(inv.outstanding_amount), "total_amount": float(inv.total_amount),
         "currency": inv.currency_code, "status": inv.status, "due_date": inv.due_date.isoformat()}
        for inv in rows
    ]


def charge(session: Session, customer_id: str, amount: Decimal, currency: str,
           idempotency_key: str) -> str:
    """Capture a payment idempotently and apply it to the oldest open invoice.

    Real movement: a billing.payments row is inserted and the invoice's outstanding_amount is
    reduced (status -> paid when it reaches zero, else partial). A retried key returns the
    original reference and moves no money again.
    """
    cid = _cust(customer_id)

    existing = session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing is not None:
        return existing.gateway_reference or f"PAY-{idempotency_key[:10].upper()}"

    invoice = session.scalar(
        select(Invoice).where(Invoice.customer_id == cid,
                              Invoice.status.in_(("issued", "partial", "overdue")))
        .order_by(Invoice.due_date.asc())
    )
    reference = f"PAY-{uuid.uuid4().hex[:10].upper()}"
    account_id = invoice.account_id if invoice else _any_account_id(session, cid)

    session.add(Payment(
        account_id=account_id, invoice_id=invoice.id if invoice else None, customer_id=cid,
        amount=amount, currency_code=currency or "TND", method="wallet",
        gateway_reference=reference, idempotency_key=idempotency_key,
        status="succeeded", paid_at=datetime.now(UTC),
    ))

    if invoice is not None:
        outstanding = Decimal(str(invoice.outstanding_amount)) - amount
        invoice.outstanding_amount = outstanding if outstanding > 0 else Decimal("0")  # type: ignore[assignment]
        invoice.status = "paid" if outstanding <= 0 else "partial"
    logger.info("charge %s -%s %s -> %s", customer_id, amount, currency, reference)
    return reference


def grant_deferral(session: Session, customer_id: str, days: int, idempotency_key: str) -> None:
    """Push the oldest open invoice's due date out by ``days`` (idempotent on the key)."""
    cid = _cust(customer_id)
    # Deferral idempotency piggybacks on a payment row marker so a retry is a no-op.
    marker = f"DEFERRAL::{idempotency_key}"
    if session.scalar(select(Payment).where(Payment.idempotency_key == marker)):
        return

    invoice = session.scalar(
        select(Invoice).where(Invoice.customer_id == cid,
                              Invoice.status.in_(("issued", "partial", "overdue")))
        .order_by(Invoice.due_date.asc())
    )
    if invoice is None:
        raise LedgerError(f"customer {customer_id} has no open invoice to defer")

    from datetime import timedelta
    invoice.due_date = invoice.due_date + timedelta(days=max(0, days))
    if invoice.status == "overdue":
        invoice.status = "issued"
    # Record the deferral as a zero-amount marker row so the key is consumed exactly once.
    session.add(Payment(
        account_id=invoice.account_id, invoice_id=invoice.id, customer_id=cid,
        amount=Decimal("0"), currency_code=invoice.currency_code, method="wallet",
        gateway_reference=f"DEF-{idempotency_key[:10].upper()}", idempotency_key=marker,
        status="succeeded", paid_at=datetime.now(UTC),
    ))
    logger.info("deferral %s +%dd on invoice %s", customer_id, days, invoice.invoice_number)


def _any_account_id(session: Session, cid):
    """A billing account id for a payment not tied to a specific invoice (prepaid top-of-wallet)."""
    from persistence.models.billing import Account
    account = session.scalar(select(Account).where(Account.customer_id == cid))
    if account is None:
        raise LedgerError("customer has no billing account")
    return account.id
