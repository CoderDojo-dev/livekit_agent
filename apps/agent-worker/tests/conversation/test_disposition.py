"""P1-2 - the disposition derived at shutdown must be truthful and always legal.

Pure unit tests over _derive_disposition: no LiveKit, no event loop, no database. The function
is a pure map from SessionUserData to one of the four values conversation.call_sessions'
CHECK constraint permits, so it can be tested exactly.
"""
from __future__ import annotations

import pytest
from server import _derive_disposition
from session import SessionUserData

# The CHECK constraint on conversation.call_sessions.final_disposition.
LEGAL = {"resolved", "escalated", "dropped", "abandoned"}


def test_graceful_close_is_resolved():
    user_data = SessionUserData()
    user_data.caller_turn_index = 4
    user_data.conversation_ending = True
    assert _derive_disposition(user_data) == "resolved"


def test_transfer_outcome_is_escalated():
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.human_transfer_outcome = "transferred"
    assert _derive_disposition(user_data) == "escalated"


def test_escalation_reason_alone_is_escalated():
    """transfer_to_human sets escalation_reason on every failure path."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.escalation_reason = "no_advisor_available"
    assert _derive_disposition(user_data) == "escalated"


def test_escalation_beats_graceful_close():
    """If a human was involved, that is the truth of the call."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.conversation_ending = True
    user_data.human_transfer_outcome = "callback_only"
    assert _derive_disposition(user_data) == "escalated"


def test_silent_caller_is_abandoned():
    assert _derive_disposition(SessionUserData()) == "abandoned"


def test_engaged_then_gone_is_dropped():
    """The pessimistic fallback: never call an unclosed call resolved."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 3
    assert _derive_disposition(user_data) == "dropped"


@pytest.mark.parametrize(
    "turns,ending,outcome,reason",
    [
        (0, False, None, None),
        (0, True, None, None),
        (5, False, None, None),
        (5, True, None, None),
        (5, False, "no_advisor", None),
        (5, False, None, "sip_unavailable"),
        (0, True, "transferred", "transfer_failed"),
    ],
)
def test_every_combination_is_a_legal_value(turns, ending, outcome, reason):
    """The function must never be able to violate the CHECK constraint."""
    user_data = SessionUserData()
    user_data.caller_turn_index = turns
    user_data.conversation_ending = ending
    user_data.human_transfer_outcome = outcome
    user_data.escalation_reason = reason
    assert _derive_disposition(user_data) in LEGAL


def test_conversation_ending_is_a_declared_field():
    """P1-2 edit 1: it must be a real dataclass field, not an attribute set by accident."""
    assert "conversation_ending" in SessionUserData.__dataclass_fields__
    assert SessionUserData().conversation_ending is False
