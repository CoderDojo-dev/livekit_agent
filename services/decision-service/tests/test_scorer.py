"""Offline tests for the decision scorer."""
from __future__ import annotations

from decision_service.scorer import recommend


def test_known_action_with_identity_scores_high() -> None:
    decision = recommend("PAYMENT_DEFERRAL", {"identity_verified": True})
    assert decision.confidence >= 0.8


def test_unknown_action_scores_low() -> None:
    assert recommend("DO_SOMETHING_WEIRD", {}).confidence < 0.5


def test_missing_identity_lowers_confidence() -> None:
    assert recommend("PAYMENT_DEFERRAL", {"identity_verified": False}).confidence < 0.7