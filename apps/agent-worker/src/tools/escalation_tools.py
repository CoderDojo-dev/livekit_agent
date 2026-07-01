"""Escalation hand-off (Blueprint section 7). Reused by every persona; records the case (P3)."""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from agents.manager_agent import ManagerAgent


def _trigger_for(user_data) -> str:
    """Pick the spec Appendix-A escalation trigger that best matches the session state."""
    if getattr(user_data, "should_offer_escalation", False):
        return "frustration"
    if getattr(user_data, "clarification_attempts", 0) >= 2:
        return "clarify_fail"
    if getattr(user_data, "identity_attempts", 0) >= 3:
        return "identity_fail"
    return "hard_failure"


@function_tool()
async def escalate_to_manager(context: RunContext) -> tuple[ManagerAgent, str]:
    """Hand off to a manager when the caller asks for a human, when the situation requires it,
    or when a persona cannot resolve the request. Records the escalation case (off the voice path)."""
    user_data = context.session.userdata
    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        writer.record_escalation(
            trigger=_trigger_for(user_data),
            target="manager_agent",
            dossier={
                "consecutive_negative_turns": getattr(user_data, "consecutive_negative_turns", 0),
                "identity_verified": getattr(user_data, "identity_verified", False),
                "clarification_attempts": getattr(user_data, "clarification_attempts", 0),
            },
            customer_id=customer.customer_id if customer else None,
        )
    return ManagerAgent(), "I'm connecting you with a specialist now."