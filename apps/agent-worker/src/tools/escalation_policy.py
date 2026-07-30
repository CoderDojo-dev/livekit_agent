"""Centralised escalation policy: one place for all thresholds and triggers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EscalationPolicy:
    max_clarifications: int = 3
    max_identity_failures: int = 3
    max_negative_turns: int = 3


_POLICY = EscalationPolicy()


def _immediate_reason(reason: str = "") -> str | None:
    motive = (reason or "").strip().lower()
    if motive in {"abuse", "threat", "fraud", "legal"}:
        return motive
    return None


def decide(user_data, explicit_reason: str = "") -> str:
    """Return the strongest escalation trigger, or empty string if none applies."""
    immediate = _immediate_reason(explicit_reason)
    if immediate:
        return immediate

    if getattr(user_data, "should_offer_escalation", False):
        return "frustration"
    if getattr(user_data, "clarification_attempts", 0) >= _POLICY.max_clarifications:
        return "clarify_fail"
    if getattr(user_data, "identity_attempts", 0) >= _POLICY.max_identity_failures:
        return "identity_fail"

    return ""
