"""Frustration must climb over a call, not snap to its extreme on one sentence.

The previous model scored any negative keyword at -1.0 (the maximum) and reset the streak to zero
on any non-negative turn. In practice that made the signal binary: a caller who said "this is
ridiculous" once was recorded at peak frustration, while a caller grumbling every other turn never
registered at all.

These tests pin the replacement's behaviour at both ends: it must not over-react to one remark,
and it must still escalate a genuinely deteriorating call at roughly the same point as before.
"""
from __future__ import annotations

import dataclasses

import pytest

from sentiment.sentiment_scorer import ESCALATION_THRESHOLD, LexicalSentimentScorer


@dataclasses.dataclass
class _UserData:
    """The fields the scorer touches. Mirrors session_state.SessionState."""

    sentiment_history: list[float] = dataclasses.field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    frustration_level: float = 0.0
    peak_frustration: float = 0.0


def _run(turns: list[str]) -> _UserData:
    userdata = _UserData()
    scorer = LexicalSentimentScorer()
    for turn in turns:
        scorer.score(turn, userdata)
    return userdata


def test_one_sharp_remark_does_not_max_out_frustration():
    userdata = _run(["this is ridiculous"])

    assert userdata.frustration_level == pytest.approx(0.22, abs=0.01)
    assert userdata.frustration_level < ESCALATION_THRESHOLD
    assert userdata.should_offer_escalation is False


def test_one_sharp_remark_does_not_escalate_even_with_a_neutral_follow_up():
    userdata = _run(["this is ridiculous", "can you check my bill"])

    assert userdata.should_offer_escalation is False


def test_three_negative_turns_still_escalate():
    """The platform was tuned around ~3 bad turns; that behaviour is preserved."""
    userdata = _run(
        ["this is ridiculous", "your service is terrible", "this is unacceptable"]
    )

    assert userdata.frustration_level >= ESCALATION_THRESHOLD
    assert userdata.should_offer_escalation is True


def test_two_negative_turns_do_not_escalate():
    userdata = _run(["this is ridiculous", "your service is terrible"])

    assert userdata.should_offer_escalation is False


def test_a_positive_turn_actually_de_escalates():
    """The old model reset the streak; this one has to REDUCE the accumulated level."""
    after_one = _run(["this is ridiculous"]).frustration_level
    after_recovery = _run(["this is ridiculous", "thank you that helps"]).frustration_level

    assert after_recovery < after_one


def test_goodwill_between_complaints_prevents_escalation():
    """Two complaints with a thank-you between them is not a call going wrong."""
    userdata = _run(["this is ridiculous", "thank you that helps", "this is terrible"])

    assert userdata.should_offer_escalation is False


def test_a_calm_stretch_decays_frustration_to_zero():
    userdata = _run(["this is ridiculous", "ok", "ok", "my number is 12345", "fine"])

    assert userdata.frustration_level == pytest.approx(0.0, abs=0.001)


def test_abuse_rises_sharply_but_not_to_the_ceiling_in_one_turn():
    """Abuse has its own immediate escalation path; the level must not pre-empt it at 1.0."""
    userdata = _run(["you are an idiot"])

    assert 0.5 <= userdata.frustration_level < 1.0


def test_peak_is_retained_after_the_caller_calms_down():
    """call_sessions.max_frustration_score records the worst the call GOT, not where it ended."""
    userdata = _run(
        ["this is ridiculous", "your service is terrible", "thanks, that is sorted"]
    )

    assert userdata.peak_frustration > userdata.frustration_level


def test_level_is_bounded_to_zero_and_one():
    hot = _run(["you are an idiot"] * 8)
    cold = _run(["thanks"] * 8)

    assert hot.frustration_level <= 1.0
    assert cold.frustration_level >= 0.0


def test_legacy_signals_are_still_maintained():
    """Callers still read sentiment_history and consecutive_negative_turns."""
    userdata = _run(["this is ridiculous", "this is terrible"])

    assert len(userdata.sentiment_history) == 2
    assert userdata.consecutive_negative_turns == 2
