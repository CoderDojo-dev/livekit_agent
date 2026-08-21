"""Sentiment scoring behind a swappable interface (Strategy; Blueprint section 1/6).

Phase 8 ships a deterministic, dependency-free LEXICAL scorer (multilingual fr/ar/en) so
sentiment never adds latency or a fragile per-turn LLM call. The production swap is an
LLM-backed scorer built in providers/ (the vendor boundary) implementing the same .score();
agent code and the hook never change when it is replaced.
"""
from __future__ import annotations

from typing import Protocol

NEGATIVE_THRESHOLD = -0.35
ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS = 3

# --------------------------------------------------------------------------------------------
# Frustration accumulation (see LexicalSentimentScorer.score).
#
# The previous model was a 3-in-a-row detector: one negative word scored -1.0 -- the maximum --
# and any non-negative turn reset the streak to zero. That is both too hot and too cold. A caller
# who says "this is ridiculous" once was recorded at peak frustration for the whole call, while a
# caller grumbling steadily but politely every other turn never registered at all.
#
# These weights make the signal accumulate instead. Three clearly negative turns still cross the
# escalation line -- the behaviour the platform was tuned around -- but a single sharp sentence no
# longer does, and goodwill actually cools the call down rather than wiping the history.
#
#   3 x negative          = 0.66  -> escalates (just over the line)
#   2 x negative          = 0.44  -> no escalation
#   negative, positive, negative = 0.26 -> no escalation, the recovery counted
#   abuse                 = 0.55  -> one step from the line, and abuse escalates on its own path
# --------------------------------------------------------------------------------------------

#: Rise per clearly negative turn.
NEGATIVE_RISE = 0.22
#: Extra rise when a turn stacks several negative cues ("useless AND a scam"). Capped once.
NEGATIVE_PILE_ON = 0.06
#: Abuse is a stronger signal, but still not a one-turn jump to the top.
ABUSE_RISE = 0.55
#: A positive turn genuinely de-escalates.
POSITIVE_RECOVERY = 0.18
#: Neutral turns cool slowly, so a calm stretch eventually clears earlier friction.
NEUTRAL_DECAY = 0.06
#: Where "offer a human" trips. Sits just under three negative turns.
ESCALATION_THRESHOLD = 0.62


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

_NEGATIVE = (
    # en
    "angry", "furious", "unacceptable", "terrible", "ridiculous", "useless", "worst",
    "frustrated", "frustrating", "scam", "hate", "awful", "incompetent",
    # fr
    "inacceptable", "ridicule", "horrible", "arnaque", "scandaleux", "marre", "énervé",
    "colère", "inadmissible", "honteux", "incompétent",
    # ar
    "سيء", "غاضب", "مرفوض", "فضيحة", "مزعج", "سخيف",
)
_POSITIVE = (
    "thanks", "thank you", "great", "perfect", "helpful", "appreciate", "excellent",
    "merci", "parfait", "génial", "super", "شكرا", "ممتاز", "رائع",
)

_ABUSE = (
    # en
    "stupid", "idiot", "moron", "shut up", "fuck", "kill", "die", "bastard",
    # fr
    "con", "connard", "stupide", "idiot", "imbécile", "ferme-la", "ta gueule",
    # ar
    "غبي", "أحمق", "اخرس",
)


def detect_abuse(transcript: str) -> tuple[str, float]:
    """Return ("abuse", 1.0) if the transcript contains abusive/threatening language, else ("", 0.0)."""
    text = transcript.lower()
    for word in _ABUSE:
        if word in text:
            return "abuse", 1.0
    return "", 0.0


class SentimentScorer(Protocol):
    """Scores a caller utterance and updates the running negative-turn signal in user-data."""

    def score(self, transcript: str, userdata) -> float: ...


class LexicalSentimentScorer:
    """Deterministic keyword scorer with an accumulating frustration level.

    `score()` still returns a per-turn sentiment value in [-1, +0.5] and still maintains
    `consecutive_negative_turns` and `should_offer_escalation`, so every existing caller keeps
    working. What changed is HOW escalation is decided: it now reads the accumulated
    `frustration_level` rather than a bare streak, so the signal climbs over a call instead of
    snapping to its extreme on one sentence.
    """

    def score(self, transcript: str, userdata) -> float:
        text = transcript.lower()

        negative_hits = sum(1 for word in _NEGATIVE if word in text)
        positive = any(word in text for word in _POSITIVE)
        abusive = any(word in text for word in _ABUSE)

        # ---- per-turn sentiment value (unchanged contract, gentler magnitude) ----
        if negative_hits or abusive:
            # Graded rather than a flat -1.0, so a single grumble is not recorded as the worst
            # possible turn. Two or more cues in one sentence read as genuinely angry.
            value = -1.0 if abusive else -_clamp(0.45 + 0.2 * (negative_hits - 1))
        elif positive:
            value = 0.5
        else:
            value = 0.0

        # ---- accumulate / decay ----
        level = getattr(userdata, "frustration_level", 0.0)
        if abusive:
            level += ABUSE_RISE
        elif negative_hits:
            level += NEGATIVE_RISE + (NEGATIVE_PILE_ON if negative_hits > 1 else 0.0)
        elif positive:
            level -= POSITIVE_RECOVERY
        else:
            level -= NEUTRAL_DECAY

        level = _clamp(level)
        userdata.frustration_level = level
        userdata.peak_frustration = max(getattr(userdata, "peak_frustration", 0.0), level)

        # ---- legacy signals, still maintained for callers that read them ----
        userdata.sentiment_history.append(value)
        if value <= NEGATIVE_THRESHOLD:
            userdata.consecutive_negative_turns += 1
        else:
            userdata.consecutive_negative_turns = 0

        # Escalation is now a function of the ACCUMULATED level, not of a streak that any single
        # neutral turn would have wiped.
        userdata.should_offer_escalation = level >= ESCALATION_THRESHOLD
        return value


def get_sentiment_scorer() -> SentimentScorer:
    """Return the configured sentiment scorer (lexical default)."""
    return LexicalSentimentScorer()
