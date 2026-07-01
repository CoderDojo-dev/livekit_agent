"""Offline tests for the Customer-360 aggregator, identity check, and read paths."""
from __future__ import annotations

from context_service.aggregator import ContextAggregator

agg = ContextAggregator()


def test_snapshot_resolves_known_caller_and_hides_secret() -> None:
    snap = agg.build_customer360("+21620155320")
    assert snap is not None
    assert snap.full_name == "Amine Ben Salah"
    assert snap.open_invoice_count == 1
    assert "4087" not in snap.model_dump_json()


def test_unknown_caller_returns_none() -> None:
    assert agg.build_customer360("+21600000000") is None


def test_identity_verification_matches_only_correct_answer() -> None:
    assert agg.verify_identity("TT-100021", "4087") is True
    assert agg.verify_identity("TT-100021", " 4087 ") is True
    assert agg.verify_identity("TT-100021", "0000") is False
    assert agg.verify_identity("UNKNOWN", "4087") is False


def test_invoice_read_path() -> None:
    invoices = agg.get_invoices("TT-100021")
    assert len(invoices) == 1
    assert invoices[0].currency == "TND"
    assert invoices[0].status == "open"


def test_balance_read_path() -> None:
    balance = agg.get_balance("TT-100045")
    assert balance is not None
    assert balance.credit > 0
    assert agg.get_balance("TT-100021") is None