"""Domain write projections (spec sections 5-7): the durable effect of an AUTHORIZED action.

Every projection does two things:

  1. **Record the transaction** - a captured payment, a deferral plan, a recharge, a SIM case -
     carrying the same idempotency_key as execution.action_ledger and the policy_verdict_id that
     authorized it.
  2. **Apply the effect to the live state** the Context façade reads back: an invoice's
     outstanding_amount/status, a prepaid balance_value, a subscription's status/plan/roaming.

Without (2) an action is only a receipt: the caller pays their bill, a payments row appears, and
the very next question still answers "you owe 42.500 TND" because billing.invoices never moved.
Read and write must agree on one system of record.

The projection runs in a SAVEPOINT inside the execute transaction, so a projection problem can
never undo the action ledger or the audit chain. Defensive: missing data logs and skips.
Live-state rows are SELECT ... FOR UPDATE so concurrent actions on one customer serialize.

Live-mode reconciliation: the legacy system may write through these same tables under the SAME
idempotency key (the sims do; their ledgers are "protected by the database's own uniqueness on
idempotency_key"). A keyed transaction row therefore means the effect is already applied, and the
projection must not apply it a second time - colliding with the unique key rolls back the whole
SAVEPOINT, and re-applying an unkeyed effect (a due-date push, a SIM order) silently doubles it.
Each projection probes first; mock mode has no such rows and behaves exactly as before.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.billing import Account, Invoice, Payment, PaymentPlan
from persistence.models.crm import Subscription
from persistence.models.ocs import BalanceAccount, Recharge
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder
from persistence.models.sim import BlockUnblockCase
from persistence.util import to_uuid

logger = logging.getLogger(__name__)

# ---- pure mapping (offline-testable) ----
_PROJECTION = {
    "EXECUTE_PAYMENT": "payment", "PAYMENT_DEFERRAL": "payment_plan",
    "TOP_UP": "recharge", "UNBLOCK_SIM": "sim_case", "REACTIVATE_SIM": "sim_case",
    "REPLACE_SIM": "sim_order",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}
_SIM_ACTION = {"UNBLOCK_SIM": "UNBLOCK", "REACTIVATE_SIM": "REACTIVATE"}

# Invoice statuses that still owe money; a payment settles these oldest-due first.
_OPEN_INVOICE_STATUSES = ("issued", "overdue", "partial")

_MONEY_Q = Decimal("0.01")      # billing.invoices / billing.payments -> Numeric(12, 2)
_BALANCE_Q = Decimal("0.0001")  # ocs.balance_accounts.balance_value  -> Numeric(14, 4)


def projection_kind(action_type: str) -> str | None:
    """Which domain table an action projects into (None if it has no projection)."""
    return _PROJECTION.get(action_type)


def sim_case_action(action_type: str) -> str | None:
    """Map a SIM action_type to the block_unblock_cases.action value."""
    return _SIM_ACTION.get(action_type)


def installment_amount(total, count) -> float:
    """Even per-installment amount (>=1 installment), rounded to millimes."""
    count = max(1, int(count or 1))
    return round(float(total or 0) / count, 3)


def money(value) -> Decimal:
    """Coerce a loose JSON amount to a non-negative Decimal (0 when absent/unusable)."""
    try:
        parsed = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)
    return parsed if parsed > 0 else Decimal(0)


def settle(amount: Decimal, outstanding: list[Decimal]) -> tuple[list[Decimal], Decimal]:
    """Allocate ``amount`` across ``outstanding`` FIFO.

    Returns (new_outstanding_per_invoice, unapplied_remainder). Pure: the DB projection applies
    the result. Overpayment leaves a remainder rather than creating a negative outstanding.
    """
    remaining = amount
    result: list[Decimal] = []
    for owed in outstanding:
        if remaining <= 0 or owed <= 0:
            result.append(owed if owed > 0 else Decimal(0))
            continue
        applied = min(owed, remaining)
        remaining -= applied
        result.append((owed - applied).quantize(_MONEY_Q))
    return result, remaining


def deferral_probe_keys(key: str) -> tuple[str, str]:
    """The execution key plus the billing system's ``DEFERRAL::``-prefixed marker form of it.

    ocs-billing-sim records a deferral as a zero-amount payment marker row whose key is
    ``DEFERRAL::<execution key>`` (ledger.grant_deferral) so the key is consumed exactly once.
    Both forms mean "this deferral was applied by the billing system".
    """
    return key, f"DEFERRAL::{key}"


# ---- DB projection ----
def project_domain_effect(session: Session, req, ledger_row) -> None:
    """Write the domain row for ``req`` (dispatch already succeeded). Caller wraps this in a savepoint."""
    kind = projection_kind(req.action_type)
    if kind == "payment":
        _payment(session, req, ledger_row)
    elif kind == "payment_plan":
        _payment_plan(session, req, ledger_row)
    elif kind == "recharge":
        _recharge(session, req, ledger_row)
    elif kind == "sim_case":
        _sim_case(session, req, ledger_row)
    elif kind == "sim_order":
        _sim_order(session, req, ledger_row)
    elif kind == "provisioning":
        _provisioning(session, req, ledger_row)


def _dec(value) -> Decimal:
    """Read a Numeric column as a Decimal (0 when NULL)."""
    return Decimal(str(value)) if value is not None else Decimal(0)


def _effect_applied(session: Session, model, key: str | None) -> bool:
    """True when a transaction row already carries this execution key.

    The keyed tables (payments / recharges / block_unblock_cases / provisioning_requests) all carry
    ``idempotency_key ... unique=True``; one unique-index lookup per action, before any write.
    """
    if not key:
        return False
    return session.scalar(select(model).where(model.idempotency_key == key)) is not None


def _deferral_applied(session: Session, key: str | None) -> bool:
    """True when the billing system already applied this deferral (either key form)."""
    if not key:
        return False
    return session.scalar(
        select(Payment).where(Payment.idempotency_key.in_(deferral_probe_keys(key)))
    ) is not None


def _account_for(session: Session, customer_id):
    cid = to_uuid(customer_id)
    return session.scalar(select(Account).where(Account.customer_id == cid)) if cid else None


def _subscription_id(session: Session, req):
    """The request's subscription, falling back to the customer's active line."""
    sid = to_uuid(req.subscription_id)
    if sid is not None:
        return sid
    cid = to_uuid(req.customer_id)
    if cid is None:
        return None
    row = session.scalar(
        select(Subscription).where(
            Subscription.customer_id == cid, Subscription.deleted_at.is_(None)
        )
    )
    return row.id if row is not None else None


def _target_invoices(session: Session, req) -> list[Invoice]:
    """Invoices a payment/deferral applies to: the named one, else every open one, oldest due first."""
    named = req.payload.get("invoice_id") or req.payload.get("invoice_number")
    if named:
        row = session.scalar(
            select(Invoice).where(Invoice.invoice_number == str(named)).with_for_update()
        )
        return [row] if row is not None else []
    cid = to_uuid(req.customer_id)
    if cid is None:
        return []
    return list(
        session.scalars(
            select(Invoice)
            .where(Invoice.customer_id == cid, Invoice.status.in_(_OPEN_INVOICE_STATUSES))
            .order_by(Invoice.due_date.asc())
            .with_for_update()
        )
    )


def _payment(session: Session, req, ledger_row) -> None:
    if _effect_applied(session, Payment, req.idempotency_key):
        # Live mode: the billing system captured the payment and settled the invoice already.
        logger.info("payment %s already applied by the billing system; projection skipped",
                    req.idempotency_key)
        return

    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("payment projection skipped: no billing account for %s", req.customer_id)
        return

    amount = money(req.payload.get("amount"))
    invoices = _target_invoices(session, req)

    # Apply the money to the live invoice state so the caller's outstanding balance moves.
    new_outstanding, unapplied = settle(amount, [_dec(inv.outstanding_amount) for inv in invoices])
    settled: list[Invoice] = []
    for invoice, owed in zip(invoices, new_outstanding, strict=False):
        if _dec(invoice.outstanding_amount) == owed:
            continue  # untouched by this payment
        invoice.outstanding_amount = owed  # type: ignore[assignment]
        invoice.status = "paid" if owed <= 0 else "partial"
        settled.append(invoice)

    if unapplied > 0:
        logger.info(
            "payment %s exceeded outstanding by %s for customer %s (recorded as credit)",
            req.idempotency_key, unapplied, req.customer_id,
        )

    session.add(Payment(
        account_id=account.id,
        invoice_id=settled[0].id if settled else None,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        method=req.payload.get("method", "card"),
        gateway_reference=ledger_row.adapter_reference,
        idempotency_key=req.idempotency_key,
        status="succeeded",
        paid_at=datetime.now(UTC),
    ))


def _payment_plan(session: Session, req, ledger_row) -> None:
    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("plan projection skipped: no billing account for %s", req.customer_id)
        return

    days = int(req.payload.get("requested_days") or 0)
    total = req.payload.get("amount") or req.payload.get("unpaid_amount") or 0
    count = req.payload.get("installment_count") or 1

    # Push the live due dates out; an overdue invoice that is now deferred is no longer overdue.
    deferral_until: date | None = None
    if _deferral_applied(session, req.idempotency_key):
        # Live mode: the billing system already pushed the due dates. Record the plan against the
        # CURRENT dates - pushing again would silently grant double the deferral.
        invoices = _target_invoices(session, req)
        deferral_until = max((inv.due_date for inv in invoices), default=None)
        logger.info("deferral %s already applied by the billing system; recording plan only",
                    req.idempotency_key)
    elif days > 0:
        for invoice in _target_invoices(session, req):
            new_due = invoice.due_date + timedelta(days=days)
            invoice.due_date = new_due
            if invoice.status == "overdue":
                invoice.status = "issued"
            if deferral_until is None or new_due > deferral_until:
                deferral_until = new_due
    else:
        logger.warning("deferral projection: non-positive requested_days for %s", req.customer_id)

    session.add(PaymentPlan(
        account_id=account.id,
        customer_id=to_uuid(req.customer_id),
        total_amount=total,
        installment_count=count,
        installment_amount=installment_amount(total, count),
        deferral_until=deferral_until,
        status="active",
        policy_verdict_id=to_uuid(req.policy_verdict_id),
    ))


def _main_balance(session: Session, subscription_id, customer_id) -> BalanceAccount | None:
    """The subscription's live main (credit) balance, opening one if the line has none yet."""
    row = session.scalar(
        select(BalanceAccount)
        .where(
            BalanceAccount.subscription_id == subscription_id,
            BalanceAccount.balance_type == "main",
        )
        .with_for_update()
    )
    if row is not None:
        return row
    cid = to_uuid(customer_id)
    if cid is None:
        return None
    row = BalanceAccount(
        subscription_id=subscription_id, customer_id=cid, balance_type="main",
        balance_value=Decimal(0), balance_unit="TND", status="active",
    )
    session.add(row)
    session.flush()
    return row


def _recharge(session: Session, req, ledger_row) -> None:
    sid = _subscription_id(session, req)
    if sid is None:
        logger.warning("recharge projection skipped: no subscription on request")
        return
    if _effect_applied(session, Recharge, req.idempotency_key):
        # Live mode: the OCS credited the balance already - INCLUDING the catalog bonus, which
        # this projection does not add. Crediting again would double the money.
        logger.info("recharge %s already applied by the OCS; projection skipped",
                    req.idempotency_key)
        return

    amount = money(req.payload.get("amount"))
    session.add(Recharge(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        channel="agent",
        idempotency_key=req.idempotency_key,
        transaction_reference=ledger_row.adapter_reference,
        status="completed",
    ))

    # Credit the live prepaid balance the Context façade reads back.
    balance = _main_balance(session, sid, req.customer_id)
    if balance is None:
        logger.warning("top-up recorded but no main balance account for subscription %s", sid)
        return
    balance.balance_value = (_dec(balance.balance_value) + amount).quantize(_BALANCE_Q)  # type: ignore[assignment]
    balance.updated_at = datetime.now(UTC)


def _sim_case(session: Session, req, ledger_row) -> None:
    action = sim_case_action(req.action_type)
    sid = _subscription_id(session, req)
    if action is None or sid is None:
        logger.warning("sim projection skipped: action=%s subscription=%s", action, req.subscription_id)
        return
    if _effect_applied(session, BlockUnblockCase, req.idempotency_key):
        logger.info("sim case %s already applied by the provisioning system; projection skipped",
                    req.idempotency_key)
        return

    session.add(BlockUnblockCase(
        subscription_id=sid,
        action=action,
        status="completed",
        identity_verified=True,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        idempotency_key=req.idempotency_key,
    ))

    # Restore the live line so Customer-360 stops reporting it blocked/suspended.
    subscription = session.get(Subscription, sid)
    if subscription is not None:
        subscription.status = "ACTIVE"


def _sim_order(session: Session, req, ledger_row) -> None:
    """REPLACE_SIM: raise a real replacement order carrying the dispatch reference."""
    # The provisioning system keys its provisioning_requests row, not the order; a keyed request
    # means the order was already placed. Without this probe, live mode ships two SIMs.
    if _effect_applied(session, ProvisioningRequest, req.idempotency_key):
        logger.info("SIM order %s already placed by the provisioning system; projection skipped",
                    req.idempotency_key)
        return
    sid = _subscription_id(session, req)
    session.add(SimOrder(
        customer_id=to_uuid(req.customer_id),
        subscription_id=sid,
        sim_type=str(req.payload.get("sim_type") or "physical"),
        status="requested",
        tracking_code=ledger_row.adapter_reference,
    ))


def _provisioning(session: Session, req, ledger_row) -> None:
    if _effect_applied(session, ProvisioningRequest, req.idempotency_key):
        # Live mode: the provisioning system recorded the request AND applied the effect
        # (plan_change_history + plan_code for CHANGE_PLAN; roaming_enabled for ACTIVATE_ROAMING).
        logger.info("provisioning %s already applied; projection skipped", req.idempotency_key)
        return

    sid = _subscription_id(session, req)
    subscription = session.get(Subscription, sid) if sid is not None else None

    session.add(ProvisioningRequest(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        action_type=req.action_type,
        status="completed",
        idempotency_key=req.idempotency_key,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        parameters=req.payload,
        completed_at=datetime.now(UTC),
    ))

    if subscription is None:
        logger.warning("provisioning effect skipped: no subscription for %s", req.customer_id)
        return

    if req.action_type == "CHANGE_PLAN":
        to_plan = str(req.payload.get("plan_code") or "unknown")
        session.add(PlanChangeHistory(
            subscription_id=sid,
            from_plan=subscription.plan_code,  # the CURRENT plan, not an absent payload field
            to_plan=to_plan,
            changed_by="agent",
            effective_date=date.today(),
        ))
        subscription.plan_code = to_plan
    elif req.action_type == "ACTIVATE_ROAMING":
        # Mirror executor.py's live dispatch exactly: the direction comes from the payload,
        # and policy (ROAM_NO_DIRECTION) guarantees it is present on an AUTHORIZED verdict.
        subscription.roaming_enabled = bool(req.payload.get("enable", True))
