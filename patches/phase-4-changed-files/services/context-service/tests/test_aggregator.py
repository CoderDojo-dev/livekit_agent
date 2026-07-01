"""Offline tests for the Customer-360 aggregator + identity check (no network/SDK)."""
from __future__ import annotations

from context_service.aggregator import ContextAggregator

agg = ContextAggregator()


def test_snapshot_resolves_known_caller_and_hides_secret() -> None:
    snap = agg.build_customer360("+21620155320")
    assert snap is not None
    assert snap.full_name == "Amine Ben Salah"
    # the identity secret must never appear on the snapshot
    assert not hasattr(snap, "id_last4")
    assert "4087" not in snap.model_dump_json()


def test_unknown_caller_returns_none() -> None:
    assert agg.build_customer360("+21600000000") is None


def test_identity_verification_matches_only_correct_answer() -> None:
    assert agg.verify_identity("TT-100021", "4087") is True
    assert agg.verify_identity("TT-100021", " 4087 ") is True
    assert agg.verify_identity("TT-100021", "0000") is False
    assert agg.verify_identity("UNKNOWN", "4087") is False