"""Deterministic, interruption-safe manager escalation."""

from __future__ import annotations

import logging

from agents.manager_agent import ManagerAgent
from livekit.agents import Agent, RunContext, function_tool

from tools.escalation_policy import EscalationPolicy, decide
from tools.voice_flow import current_chat_ctx, handoff_with_message

logger = logging.getLogger(__name__)

_POLICY = EscalationPolicy()
_MAX_OFFERS = 3

_OFFER_FIRST = {
    "fr": "Do not transfer yet. In ONE short French sentence, say plainly what you cannot "
          "do, then ask if they would like to speak with a manager. Wait for their answer.",
    "ar": "Do not transfer yet. In ONE short Arabic sentence, say plainly what you cannot "
          "do, then ask if they would like to speak with a manager. Wait for their answer.",
    "en": "Do not transfer yet. In ONE short English sentence, say plainly what you cannot "
          "do, then ask if they would like to speak with a manager. Wait for their answer.",
}

_KEEP_HELPING = {
    "fr": "Pas de problème. Je continue à vous aider. Dites-moi ce dont vous avez besoin.",
    "ar": "لا مشكلة. سأستمر في مساعدتك. أخبرني بما تحتاجه.",
    "en": "No problem. I will keep helping you. Tell me what you need.",
}


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


_HARD_FAILURE = {
    "fr": "Je comprends. Malheureusement, je ne peux pas vous transférer pour le moment. "
          "Veuillez rappeler plus tard ou contacter notre service client par un autre canal.",
    "ar": "أتفهم ذلك. لسوء الحظ، لا يمكنني تحويلك في الوقت الحالي. "
          "يرجى الاتصال لاحقًا أو الاتصال بخدمة العملاء عبر قناة أخرى.",
    "en": "I understand. Unfortunately, I cannot transfer you right now. "
          "Please call back later or contact our customer service through another channel.",
}


@function_tool()
async def escalate_to_manager(
    context: RunContext,
    reason: str = "caller_request",
    caller_agreed: bool = False,
) -> Agent | str:
    """Hand the call over to a manager.

    Only call this when the caller has agreed to speak with a manager (caller_agreed=true),
    or when the caller is abusive, threatening or the request looks fraudulent
    (reason="abuse" / "threat" / "fraud", caller_agreed may stay false).
    """
    user_data = context.session.userdata
    trigger = decide(user_data, reason)

    if not caller_agreed and trigger not in {"abuse", "threat", "fraud", "legal"}:
        language = _resolve_language(context)
        if getattr(user_data, "user_refused_manager", False):
            return _KEEP_HELPING.get(language, _KEEP_HELPING["en"])
        if getattr(user_data, "offer_count", 0) >= _MAX_OFFERS:
            logger.info("escalation hard-failure (reason=%s, offers exhausted)", trigger or "unspecified")
            return _HARD_FAILURE.get(language, _HARD_FAILURE["en"])
        user_data.offer_count += 1
        logger.info("escalation deferred (reason=%s, offer %d/%d)",
                     trigger or "unspecified", user_data.offer_count, _MAX_OFFERS)
        return _OFFER_FIRST.get(language, _OFFER_FIRST["fr"])

    user_data.current_persona_skill_tag = _skill_tag_for(context)
    user_data.human_transfer_announced = True

    next_agent = ManagerAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))

    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        try:
            writer.record_escalation(
                trigger=trigger,
                target="manager_agent",
                dossier={
                    "consecutive_negative_turns": getattr(user_data, "consecutive_negative_turns", 0),
                    "identity_verified": getattr(user_data, "identity_verified", False),
                    "clarification_attempts": getattr(user_data, "clarification_attempts", 0),
                },
                customer_id=customer.customer_id if customer else None,
            )
        except Exception as exc:
            logger.warning("escalation record skipped: %s", exc)

    return await handoff_with_message(
        context,
        next_agent,
        _MANAGER_LINES[_resolve_language(context)],
        language=_resolve_language(context),
        loop_guard=False,
    )


@function_tool()
async def caller_refused_manager(context: RunContext) -> str:
    """The caller does NOT want to speak with a manager. Acknowledge and continue helping."""
    user_data = context.session.userdata
    user_data.user_refused_manager = True
    user_data.can_hardfail = False
    user_data.should_offer_escalation = False
    language = _resolve_language(context)
    logger.info("caller refused manager; will not offer again")
    return _KEEP_HELPING.get(language, _KEEP_HELPING["en"])
