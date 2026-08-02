"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from conversation.writer import sentiment_label
from livekit.agents import Agent
from livekit.agents.types import NotGivenOr
from sentiment.sentiment_scorer import get_sentiment_scorer
from tools.escalation_policy import decide
from tools.session_flow_tools import end_conversation, switch_spoken_language

from agents.instruction_kit import (
    CLOSING_PROTOCOL,
    KNOWLEDGE_ABSTENTION_RULE,
    LANGUAGE_SWITCH_POLICY,
    TTS_LANGUAGE_REMINDER,
    build_persona_instructions,
    enforce_contract,
    tool_names,
)

__all__ = [
    "BaseTelecomAgent",
    "CLOSING_PROTOCOL",
    "KNOWLEDGE_ABSTENTION_RULE",
    "LANGUAGE_SWITCH_POLICY",
    "NO_DEAD_END_MANDATE",
    "merge_instructions",
]

logger = logging.getLogger(__name__)

# DEPRECATED (v64): frozen mandate kept only for backward compatibility with
# historical check scripts and as the non-regression reference for the generated
# Triage mandate. Do NOT inject this into a new persona: it names route_* tools
# that most personas do not own. Personas now derive their mandate from their own
# tool set via agents.instruction_kit.routing_mandate.
NO_DEAD_END_MANDATE = (
    "\n\nRouting mandate (you MUST follow this):\n"
    "- If the caller asks about their BALANCE, INVOICE, PAYMENT, or DEFERRAL, "
    "call route_to_billing immediately.\n"
    "- If the caller asks about their PLAN, RECHARGE, ROAMING, or PHONE LINE, "
    "call route_to_account_services immediately.\n"
    "- If the caller has a SIM, NETWORK, or CONNECTIVITY problem, "
    "call route_to_technical immediately.\n"
    "- If the request is ambiguous, call request_clarification.\n"
    "- NEVER tell the caller to call a different department or number yourself. "
    "Use the route_* tool. If none of the above fits, call escalate_to_manager.\n"
    "- The route_* tools transfer the caller to the right specialist; after calling "
    "one you will NOT speak again, so do not also say goodbye yourself."
)


def merge_instructions(persona_core: str, tts_provided: bool = True) -> str:
    """DEPRECATED (v64). Assemble the instruction block with the FROZEN mandate.

    Behaviour is byte-identical to v63 on purpose, so existing callers and check
    scripts keep passing. New code must pass ``core_instructions`` to
    BaseTelecomAgent, which derives the mandate from the registered tools.
    """
    parts = [persona_core, NO_DEAD_END_MANDATE, CLOSING_PROTOCOL, LANGUAGE_SWITCH_POLICY]
    if tts_provided:
        parts.append(TTS_LANGUAGE_REMINDER)
    return "\n".join(parts)


def _extract_text(message) -> str:
    """Best-effort extraction of the user's text from a ChatMessage (content may be str or list)."""
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part for part in content if isinstance(part, str))
    return ""


class BaseTelecomAgent(Agent):
    """Every persona inherits this to share the sentiment/escalation + logging observer."""

    def __init__(
        self,
        *,
        instructions: str | None = None,
        core_instructions: str | None = None,
        capabilities: Iterable[str] = (),
        tools=None,
        **kwargs,
    ) -> None:
        """Single funnel for persona construction.

        ``core_instructions`` is the persona's own domain prose. Every shared
        layer -- routing mandate, closing protocol, language policy, TTS lock,
        knowledge abstention -- is DERIVED from the final tool set, so a persona
        can no longer be ordered to call a tool it does not own.

        ``capabilities`` declares tool names that cannot be introspected from the
        tool objects themselves (MCP toolsets, whose tool list only exists once
        the server is reached), e.g. ``{"knowledge_search"}``.

        ``instructions`` remains accepted for callers that assemble their own
        block; such a block is still validated against the tool set.
        """
        merged_tools = list(tools or [])
        if end_conversation not in merged_tools:
            merged_tools.append(end_conversation)
        if switch_spoken_language not in merged_tools:
            merged_tools.append(switch_spoken_language)

        capability_names = tuple(capabilities)
        available = tool_names(merged_tools, extra=capability_names)

        if core_instructions is not None:
            if instructions is not None:
                raise ValueError(
                    "pass either core_instructions or instructions, not both"
                )
            instructions = build_persona_instructions(
                core_instructions,
                available,
                tts_provided=kwargs.get("tts") is not None,
            )
        elif instructions is None:
            raise ValueError("a persona needs core_instructions or instructions")

        enforce_contract(type(self).__name__, instructions, available)

        # Exposed for tests and runtime diagnostics; not used by the SDK.
        self._capabilities = capability_names
        self._available_tool_names = available

        language = kwargs.pop("language", None)
        super().__init__(
            instructions=instructions,
            tools=merged_tools,
            **kwargs,
        )
        if language:
            _LANG_MAP = {"fr": "French", "ar": "Arabic", "en": "English"}
            selected = language if language in _LANG_MAP else "fr"
            self._language = selected
            self._lang_name = _LANG_MAP[selected]

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the turn, log it (off-path), and inject a de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        user_data.caller_turn_index = getattr(user_data, "caller_turn_index", 0) + 1

        # Patch #5 — le compteur de clarifications doit mesurer les deferrals
        # CONSÉCUTIFS sur le sujet courant, pas le total de l'appel. Si le client
        # répond à une clarification qu'on vient de poser, on conserve le streak ;
        # sinon il est passé à un tour normalement traité -> on réinitialise.
        if getattr(user_data, "_clarification_pending", False):
            user_data._clarification_pending = False
        else:
            user_data.clarification_attempts = 0

        transcript = _extract_text(new_message).strip()
        if transcript:
            logger.info("caller_transcript=%s", transcript)
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:
                logger.debug("sentiment scoring skipped: %s", exc)

            writer = getattr(user_data, "conversation_writer", None)
            if writer is not None:
                score = user_data.sentiment_history[-1] if getattr(user_data, "sentiment_history", None) else 0.0
                writer.record_turn(
                    speaker="caller", text=transcript,
                    active_agent=type(self).__name__, language=getattr(user_data, "language", None),
                )
                writer.record_sentiment(score=score, label=sentiment_label(score))

        if decide(user_data) == "frustration":
            try:
                lang = getattr(self, "_lang_name", None)
                if not lang and user_data is not None:
                    lang_code = getattr(user_data, "language", "fr")
                    val = getattr(lang_code, "value", lang_code)
                    _MAP = {"fr": "French", "ar": "Arabic", "en": "English"}
                    lang = _MAP.get(str(val).lower().strip()[:2], "French")
                lang = lang or "French"
                note = (
                    "The caller appears repeatedly frustrated. In your next reply, strictly in "
                    f"{lang} ONLY, sincerely acknowledge their frustration, stay brief and calm, "
                    "and proactively offer to connect them with a human specialist. If they agree, "
                    "call escalate_to_manager. Never switch language."
                )
                turn_ctx.add_message(role="system", content=note)
                logger.info("frustration high -> injected proactive de-escalation note (%s)", lang)
            except Exception as exc:
                logger.debug("frustration injection skipped: %s", exc)
