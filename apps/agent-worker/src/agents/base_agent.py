"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging

from conversation.writer import sentiment_label
from livekit.agents import Agent
from sentiment.sentiment_scorer import get_sentiment_scorer
from tools.session_flow_tools import end_conversation

logger = logging.getLogger(__name__)

_DEESCALATION_NOTE = (
    "The caller appears repeatedly frustrated. In your next reply, sincerely acknowledge their "
    "frustration, stay brief and calm, and proactively offer to connect them with a human "
    "specialist. If they agree, call escalate_to_manager."
)

# Shared closing protocol appended to every persona's instructions so ending a
# call behaves identically no matter which specialist is active.
CLOSING_PROTOCOL = (
    "\n\nEnding the call: when the caller's need is fully handled — information "
    "delivered, a ticket created, an issue escalated, a callback scheduled, or "
    "the caller signals they are finished — first ask, in the caller's language, "
    "whether there is anything else you can help with. If they need more, "
    "continue normally. Only once the caller clearly has nothing else, or clearly "
    "wants to leave or says goodbye, call end_conversation to close the call. "
    "Judge this from the caller's intent, not from a fixed list of keywords. "
    "Never call end_conversation while the caller still needs help, and never end "
    "without first confirming there is nothing else. When you call "
    "end_conversation, do not also speak a goodbye yourself — the tool delivers "
    "the farewell."
)


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

    def __init__(self, *, instructions: str, tools=None, **kwargs) -> None:
        """Give every persona the shared closing protocol + end_conversation tool.

        Personas keep passing their own instructions/tools; this centralizes the
        graceful-end capability so it stays consistent and never drifts per persona.
        """
        merged_tools = list(tools or [])
        if end_conversation not in merged_tools:
            merged_tools.append(end_conversation)
        language = kwargs.pop("language", None)
        super().__init__(
            instructions=instructions + CLOSING_PROTOCOL,
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

        if getattr(user_data, "should_offer_escalation", False):
            try:
                lang = getattr(self, "_lang_name", None)
                if not lang and user_data is not None:
                    l = getattr(user_data, "language", "fr")
                    val = getattr(l, "value", l)
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
