"""Deterministic clarification counter (CDC section 10.1: two failed clarifications -> ESCALATE).

Asking via this tool (instead of free-text) is what makes the mandatory-escalation trigger real:
the second unresolved clarification returns an 'escalate' outcome, and clarification_attempts also
feeds the policy context so the engine's ESC_CLARIFICATION rule is reachable.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool


@function_tool()
async def request_clarification(context: RunContext, question: str) -> dict:
    """Ask the caller ONE clarifying question when their request is ambiguous.

    Call this INSTEAD of asking directly, so attempts are counted. After two unresolved
    clarifications the request must be escalated (outcome 'escalate').
    """
    user_data = context.session.userdata
    user_data.clarification_attempts += 1
    if user_data.clarification_attempts >= 2:
        return {
            "outcome": "escalate",
            "reason": "two_failed_clarifications",
            "message": "Still unclear after two attempts - call escalate_to_manager.",
        }
    return {
        "outcome": "ask",
        "question": question,
        "message": "Ask the caller this one clarifying question, in their language.",
    }