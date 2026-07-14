"""Deterministic, interruption-safe manager escalation."""
from __future__ import annotations

import logging

from agents.manager_agent import ManagerAgent
from livekit.agents import Agent, RunContext, function_tool

from tools.voice_flow import current_chat_ctx

logger = logging.getLogger(__name__)


def _trigger_for(user_data) -> str:
    """Select the strongest verified escalation trigger."""
    if getattr(user_data, "should_offer_escalation", False):
        return "frustration"
    if getattr(user_data, "clarification_attempts", 0) >= 2:
        return "clarify_fail"
    if getattr(user_data, "identity_attempts", 0) >= 3:
        return "identity_fail"
    return "hard_failure"


def _resolve_language(context: RunContext) -> str:
    user_data = getattr(context.session, "userdata", None)
    if user_data is not None:
        lang = getattr(user_data, "language", "fr")
        val = getattr(lang, "value", lang)
        if isinstance(val, str) and val.lower().strip()[:2] in {"fr", "ar", "en"}:
            return val.lower().strip()[:2]
    return "fr"


@function_tool()
async def escalate_to_manager(context: RunContext) -> Agent:
    """Record the escalation and hand off to the manager on the same session."""
    user_data = context.session.userdata
    next_agent = ManagerAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))

    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        try:
            writer.record_escalation(
                trigger=_trigger_for(user_data),
                target="manager_agent",
                dossier={
                    "consecutive_negative_turns": getattr(
                        user_data, "consecutive_negative_turns", 0
                    ),
                    "identity_verified": getattr(
                        user_data, "identity_verified", False
                    ),
                    "clarification_attempts": getattr(
                        user_data, "clarification_attempts", 0
                    ),
                },
                customer_id=customer.customer_id if customer else None,
            )
        except Exception as exc:
            # Persistence is off the real-time path and must never block a handoff.
            logger.warning("escalation record skipped: %s", exc)

    return next_agent
