"""Shared base persona: per-turn sentiment scoring + proactive de-escalation (cookbook section 12).

on_user_turn_completed is a LiveKit lifecycle hook that runs after the caller's turn and BEFORE
the persona's reply. We score the turn there (updating the frustration signal in user-data) and,
when frustration is flagged, inject a transient system note so the persona proactively
acknowledges it and offers a human. The note lives only for the current turn (not persisted).
This is the Observer half of Blueprint section 6: the hook measures, the persona acts.
"""
from __future__ import annotations

import logging

from livekit.agents import Agent

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
    """Every persona inherits this to share the sentiment/escalation observer behaviour."""

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the caller's turn; inject a proactive de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        transcript = _extract_text(new_message).strip()
        if transcript:
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:  # noqa: BLE001 - sentiment must never break the call
                logger.debug("sentiment scoring skipped: %s", exc)

        if getattr(user_data, "should_offer_escalation", False):
            try:
                turn_ctx.add_message(role="system", content=_DEESCALATION_NOTE)
                logger.info("frustration high -> injected proactive de-escalation note")
            except Exception as exc:  # noqa: BLE001 - injection is best-effort
                logger.debug("frustration injection skipped: %s", exc)