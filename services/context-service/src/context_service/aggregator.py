"""Customer-360 aggregation façade (Blueprint section 4.3).

Reads the caller profile, enriches it with invoice/balance summaries, answers the
server-side identity check, and serves read-only invoice/balance lookups. The snapshot it
returns never includes the identity secret.
"""
from __future__ import annotations

from context_service import mock_directory
from context_service.schemas import Balance, Customer360, Invoice


class ContextAggregator:
    """Builds the Customer360 snapshot, performs identity checks, serves read-only lookups."""

    def build_customer360(self, msisdn: str) -> Customer360 | None:
        """Return the enriched snapshot for the caller owning ``msisdn`` or None."""
        customer = mock_directory.find_by_msisdn(msisdn)
        if customer is None:
            return None
        invoices = mock_directory.invoices_for(customer.customer_id)
        balance = mock_directory.balance_for(customer.customer_id)
        balance_summary = (
            f"{balance['credit']:.3f} {balance['currency']}" if balance else None
        )
        return Customer360(
            customer_id=customer.customer_id,
            full_name=customer.full_name,
            msisdn=customer.msisdn,
            subscription_type=customer.subscription_type,
            preferred_language=customer.preferred_language,
            is_vip=customer.is_vip,
            account_age_days=customer.account_age_days,
            open_invoice_count=len([i for i in invoices if i["status"] != "paid"]),
            balance_summary=balance_summary,
        )

    def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Return True iff ``answer`` matches the customer's on-file identity secret."""
        customer = mock_directory.find_by_id(customer_id)
        return customer is not None and answer.strip() == customer.id_last4

    def get_invoices(self, customer_id: str) -> list[Invoice]:
        """Return the customer's invoices (read-only, CDC section 5.1)."""
        return [Invoice(**inv) for inv in mock_directory.invoices_for(customer_id)]

    def get_balance(self, customer_id: str) -> Balance | None:
        """Return the customer's prepaid balance or None."""
        data = mock_directory.balance_for(customer_id)
        return Balance(**data) if data else None