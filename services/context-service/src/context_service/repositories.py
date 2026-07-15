"""CrmRepository: all CRM/Billing/OCS reads behind the Context façade (spec sections 4-6).

Replaces the volatile mock_directory. The service contract (Customer360 / invoices / balance /
verify) is unchanged; identity is now resolved msisdn -> (customer_id, subscription_id) once.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_service import mapping
from context_service.schemas import Balance, Customer360, Invoice
from persistence.models.billing import Invoice as InvoiceRow
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount


class CrmRepository:
    """Read-side repository over the crm/billing/ocs schemas."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- identity ---
    def resolve_identity(self, msisdn: str) -> tuple[Customer, Subscription] | None:
        """Resolve a caller MSISDN to (customer, subscription); None if no active line."""
        stmt = (
            select(Customer, Subscription)
            .join(Subscription, Subscription.customer_id == Customer.id)
            .where(Subscription.msisdn == msisdn.strip(), Subscription.deleted_at.is_(None))
        )
        row = self._session.execute(stmt).first()
        return (row[0], row[1]) if row else None

    def _customer(self, customer_id: str) -> Customer | None:
        return self._session.get(Customer, customer_id)

    # --- Customer-360 ---
    def build_customer360(self, msisdn: str) -> Customer360 | None:
        """Build the snapshot for the caller owning ``msisdn`` (None if unknown)."""
        resolved = self.resolve_identity(msisdn)
        if resolved is None:
            return None
        customer, subscription = resolved

        invoices = self._invoice_rows(customer.id)
        open_count = sum(1 for inv in invoices if mapping.invoice_status(inv.status) != "paid")
        balance = self._balance_summary(subscription.id)

        return Customer360(
            customer_id=str(customer.id),
            subscription_id=str(subscription.id),
            full_name=f"{customer.first_name} {customer.last_name}",
            msisdn=subscription.msisdn,
            subscription_type=subscription.plan_code or subscription.plan_type,
            preferred_language=customer.preferred_language,
            is_vip=customer.vip_flag,
            fraud_suspected=customer.fraud_suspected,
            account_age_days=mapping.account_age_days(subscription.activation_date),
            open_invoice_count=open_count,
            balance_summary=balance,
        )

    def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Server-side step-up check against the on-file national id (CIN)."""
        customer = self._customer(customer_id)
        return customer is not None and mapping.verify_answer(customer.national_id, answer)

    # --- reads ---
    def _invoice_rows(self, customer_id) -> list[InvoiceRow]:
        # Most recent first: the agent presents invoices[0] as "your latest invoice",
        # so the order has to be deterministic rather than whatever the heap returns.
        stmt = (
            select(InvoiceRow)
            .where(InvoiceRow.customer_id == customer_id)
            .order_by(InvoiceRow.issue_date.desc())
        )
        return list(self._session.scalars(stmt))

    def get_invoices(self, customer_id: str) -> list[Invoice]:
        """Return the customer's invoices, most recent first (read-only, CDC section 5.1)."""
        return [
            Invoice(
                invoice_id=row.invoice_number,
                amount=float(row.total_amount),
                outstanding=float(row.outstanding_amount or 0),
                currency=row.currency_code,
                due_date=row.due_date.isoformat(),
                status=mapping.invoice_status(row.status),
            )
            for row in self._invoice_rows(customer_id)
        ]

    def get_balance(self, customer_id: str) -> Balance | None:
        """Return the prepaid balance (main credit + data) or None."""
        rows = list(
            self._session.scalars(
                select(BalanceAccount).where(BalanceAccount.customer_id == customer_id)
            )
        )
        if not rows:
            return None
        credit, currency, data_mb, valid_until = 0.0, "TND", 0, None
        for row in rows:
            if row.balance_type == "main":
                credit, currency = float(row.balance_value), row.balance_unit
            elif row.balance_type == "data":
                data_mb = mapping.to_megabytes(float(row.balance_value), row.balance_unit)
            if row.expiry_date and valid_until is None:
                valid_until = row.expiry_date.isoformat()
        return Balance(
            customer_id=customer_id, credit=credit, currency=currency,
            data_remaining_mb=data_mb, valid_until=valid_until,
        )

    def _balance_summary(self, subscription_id) -> str | None:
        row = self._session.scalar(
            select(BalanceAccount).where(
                BalanceAccount.subscription_id == subscription_id,
                BalanceAccount.balance_type == "main",
            )
        )
        return f"{float(row.balance_value):.3f} {row.balance_unit}" if row else None