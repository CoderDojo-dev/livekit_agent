"""Customer-360 aggregation façade (Blueprint section 4.3).

Reads the caller profile (and, from Phase 5, billing/balance/tickets) and answers the
server-side identity check. The snapshot it returns never includes the identity secret.
"""
from __future__ import annotations

from context_service import mock_directory
from context_service.schemas import Customer360


class ContextAggregator:
    """Builds the Customer360 snapshot and performs the step-up identity check."""

    def build_customer360(self, msisdn: str) -> Customer360 | None:
        """Return the snapshot for the caller owning ``msisdn`` or None if unknown."""
        customer = mock_directory.find_by_msisdn(msisdn)
        if customer is None:
            return None
        return Customer360(
            customer_id=customer.customer_id,
            full_name=customer.full_name,
            msisdn=customer.msisdn,
            subscription_type=customer.subscription_type,
            preferred_language=customer.preferred_language,
            is_vip=customer.is_vip,
            account_age_days=customer.account_age_days,
            # open_invoice_count / balance_summary enriched in Phase 5
        )

    def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Return True iff ``answer`` matches the customer's on-file identity secret."""
        customer = mock_directory.find_by_id(customer_id)
        return customer is not None and answer.strip() == customer.id_last4