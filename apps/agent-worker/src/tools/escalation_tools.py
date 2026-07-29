"""Deterministic, interruption-safe manager escalation."""

from __future__ import annotations

import logging

from agents.manager_agent import ManagerAgent
from livekit.agents import Agent, RunContext, function_tool

from tools.voice_flow import current_chat_ctx, handoff_with_message

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


_MANAGER_LINES = {
    "fr": "Je comprends. Je vous transfère à un conseiller qui va poursuivre avec vous.",
    "ar": "أتفهم ذلك. سأحوّلك إلى مستشار سيتابع معك.",
    "en": "I understand. I'm transferring you to an advisor who will continue with you.",
}

# Advisor skill required for a human transfer, derived from the persona that escalates.
# session_state.current_persona_skill_tag defaults to "general" and was never assigned
# anywhere, so every escalation used to claim a generalist advisor whatever the domain.
_SKILL_TAGS = {
    "BillingAgent": "billing",
    "TechnicalAgent": "technical",
    "AccountServicesAgent": "account",
}


def _skill_tag_for(context: RunContext) -> str:
    """Skill tag of the persona currently escalating ("general" for triage/unknown)."""
    current = getattr(context.session, "current_agent", None)
    return _SKILL_TAGS.get(type(current).__name__, "general")


@function_tool()
async def escalate_to_manager(context: RunContext) -> Agent:
    """Record the escalation and hand off to the manager on the same session."""
    user_data = context.session.userdata

    # The human transfer needs the skill of the persona we are leaving, and the
    # handoff line below IS the transition announcement - so tell transfer_to_human
    # not to speak a second one.
    user_data.current_persona_skill_tag = _skill_tag_for(context)
    user_data.human_transfer_announced = True

    next_agent = ManagerAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))

    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        try:
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
        except Exception as exc:
            # Persistence is off the real-time path and must never block a handoff.
            logger.warning("escalation record skipped: %s", exc)

    return await handoff_with_message(context, next_agent, _MANAGER_LINES[_resolve_language(context)])
