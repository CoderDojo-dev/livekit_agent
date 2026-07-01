"""Sentiment scoring behind a swappable interface (Strategy; Blueprint section 1/6).

Phase 8 ships a deterministic, dependency-free LEXICAL scorer (multilingual fr/ar/en) so
sentiment never adds latency or a fragile per-turn LLM call. The production swap is an
LLM-backed scorer built in providers/ (the vendor boundary) implementing the same .score();
agent code and the hook never change when it is replaced.
"""
from __future__ import annotations

from typing import Protocol

NEGATIVE_THRESHOLD = -0.35
ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS = 2

_NEGATIVE = (
    # en
    "angry", "furious", "unacceptable", "terrible", "ridiculous", "useless", "worst",
    "frustrated", "frustrating", "scam", "cancel", "hate", "awful", "incompetent", "complaint",
    # fr
    "inacceptable", "ridicule", "horrible", "arnaque", "scandaleux", "marre", "énervé",
    "colère", "inadmissible", "résilier", "honteux", "incompétent", "nul",
    # ar
    "سيء", "غاضب", "مرفوض", "فضيحة", "مزعج", "سخيف",
)
_POSITIVE = (
    "thanks", "thank you", "great", "perfect", "helpful", "appreciate", "excellent",
    "merci", "parfait", "génial", "super", "شكرا", "ممتاز", "رائع",
)


class SentimentScorer(Protocol):
    """Scores a caller utterance and updates the running negative-turn signal in user-data."""

    def score(self, transcript: str, userdata) -> float: ...


class LexicalSentimentScorer:
    """Deterministic keyword scorer: -1.0 (negative), +0.5 (positive), 0.0 (neutral)."""

    def score(self, transcript: str, userdata) -> float:
        text = transcript.lower()
        negative = any(word in text for word in _NEGATIVE)
        positive = any(word in text for word in _POSITIVE)
        value = -1.0 if negative else (0.5 if positive else 0.0)

        userdata.sentiment_history.append(value)
        if value <= NEGATIVE_THRESHOLD:
            userdata.consecutive_negative_turns += 1
        else:
            userdata.consecutive_negative_turns = 0
        userdata.should_offer_escalation = (
            userdata.consecutive_negative_turns >= ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS
        )
        return value


def get_sentiment_scorer() -> SentimentScorer:
    """Return the configured sentiment scorer (lexical default)."""
    return LexicalSentimentScorer()