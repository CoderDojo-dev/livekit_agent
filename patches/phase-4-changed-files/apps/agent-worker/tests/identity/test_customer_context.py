"""Offline test: the worker maps a context-service snapshot into CustomerContext (no SDK)."""
from __future__ import annotations

from session.customer_context import CustomerContext


def test_from_snapshot_maps_fields_and_ignores_enrichment() -> None:
    snapshot = {
        "customer_id": "TT-100021",
        "full_name": "Amine Ben Salah",
        "msisdn": "+21620155320",
        "subscription_type": "Postpaid Flexi",
        "preferred_language": "fr",
        "is_vip": False,
        "account_age_days": 1420,
        "open_invoice_count": 0,
        "balance_summary": None,
    }
    ctx = CustomerContext.from_snapshot(snapshot)
    assert ctx.customer_id == "TT-100021"
    assert ctx.full_name == "Amine Ben Salah"
    assert ctx.preferred_language == "fr"