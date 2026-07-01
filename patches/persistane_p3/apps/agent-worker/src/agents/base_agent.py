"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging

from livekit.agents import Agent

from conversation.writer import sentiment_label
from sentiment.sentiment_scorer import get_sentiment_scorer

logger = logging.getLogger(__name__)

_DEESCALATION_NOTE = (
    "The caller appears repeatedly frustrated. In your next reply, sincerely acknowledge their "
    "frustration, stay brief and calm, and proactively offer to connect them with a human "
    "specialist. If they agree, call escalate_to_manager."
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

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the turn, log it (off-path), and inject a de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        transcript = _extract_text(new_message).strip()
        if transcript:
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:  # noqa: BLE001 - sentiment must never break the call
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
                turn_ctx.add_message(role="system", content=_DEESCALATION_NOTE)
                logger.info("frustration high -> injected proactive de-escalation note")
            except Exception as exc:  # noqa: BLE001
                logger.debug("frustration injection skipped: %s", exc)