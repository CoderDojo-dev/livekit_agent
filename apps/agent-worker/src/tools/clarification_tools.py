"""Deterministic, interruption-safe clarification and escalation.

The first clarification is spoken directly, then StopResponse terminates the
tool-only turn without creating an empty LLM-to-TTS stream. The third failed
clarification offers the caller a transfer instead of forcing one.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from tools.escalation_policy import decide
from tools.escalation_tools import _MAX_OFFERS, _OFFER_FIRST, _resolve_language, escalate_to_manager
from tools.voice_flow import say_and_stop

_OFFER_CLARIFY = {
    "fr": "Do not transfer yet. Tell the caller plainly you are having trouble understanding, "
          "then ask if they would like to speak with a manager. Wait for their answer.",
    "ar": "Do not transfer yet. Tell the caller plainly you are having trouble understanding, "
          "then ask if they would like to speak with a manager. Wait for their answer.",
    "en": "Do not transfer yet. Tell the caller plainly you are having trouble understanding, "
          "then ask if they would like to speak with a manager. Wait for their answer.",
}


@function_tool()
async def request_clarification(
    context: RunContext,
    question: str,
) -> Agent | str | None:
    """Ask one clarification. Offer escalation deterministically after the third attempt."""
    user_data = context.session.userdata
    user_data.clarification_attempts += 1
    user_data._clarification_pending = True

    if user_data.clarification_attempts >= 3:
        language = _resolve_language(context)
        trigger = decide(user_data)
        if not trigger or trigger == "frustration":
            if not getattr(user_data, "user_refused_manager", False) and getattr(user_data, "offer_count", 0) < _MAX_OFFERS:
                user_data.offer_count += 1
                return _OFFER_FIRST.get(language, _OFFER_FIRST["fr"])
        if trigger == "clarify_fail":
            return _OFFER_CLARIFY.get(language, _OFFER_CLARIFY["en"])
        return await escalate_to_manager(context, reason=trigger, caller_agreed=False)

    normalized = (question or "").strip()
    if not normalized:
        normalized = "Pouvez-vous préciser votre demande, s'il vous plaît ?"

    await say_and_stop(context, normalized)

    return None
