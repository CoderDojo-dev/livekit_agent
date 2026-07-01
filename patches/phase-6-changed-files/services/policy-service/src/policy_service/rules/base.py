"""Shared rule result type and verdict constants."""
from __future__ import annotations

from dataclasses import dataclass

AUTHORIZED = "authorized"
REFUSED = "refused"
ESCALATE = "escalate"


@dataclass(frozen=True)
class VerdictResult:
    """A rule outcome: verdict + the rule that produced it + a human-readable justification."""

    verdict: str
    rule_id: str
    justification: str