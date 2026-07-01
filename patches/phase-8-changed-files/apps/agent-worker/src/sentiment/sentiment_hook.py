"""Attach post-turn sentiment scoring to an AgentSession (cookbook section 12).

[VERIFY] event name: 'user_input_transcribed' is the v1 finalized-user-turn event. The hook
only measures (updates consecutive_negative_turns / should_offer_escalation); the policy
engine's ESC_FRUSTRATION rule and the personas act on the signal. Never raises into the call.
"""
from __future__ import annotations

import logging

from sentiment.sentiment_scorer import get_sentiment_scorer

logger = logging.getLogger(__name__)


def attach_sentiment(session) -> None:
    """Wire lexical sentiment scoring onto each finalized caller turn."""
    scorer = get_sentiment_scorer()

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev) -> None:
        if not getattr(ev, "is_final", True):
            return
        transcript = (getattr(ev, "transcript", "") or "").strip()
        if not transcript:
            return
        user_data = getattr(session, "userdata", None)
        if user_data is None:
            return
        try:
            score = scorer.score(transcript, user_data)
            if user_data.should_offer_escalation:
                logger.info(
                    "sentiment: negative_turns=%s -> escalation recommended",
                    user_data.consecutive_negative_turns,
                )
            else:
                logger.debug("sentiment score=%.2f", score)
        except Exception as exc:  # noqa: BLE001 - sentiment must never break the call
            logger.debug("sentiment scoring skipped: %s", exc)