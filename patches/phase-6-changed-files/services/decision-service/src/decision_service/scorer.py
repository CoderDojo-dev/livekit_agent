"""Decision context (CDC section 4.5): rank a candidate action with a confidence value.

Deterministic for Phase 6: a known, catalogued action with a resolved caller scores high;
an unknown action or missing context scores low so the façade escalates instead of forcing.
"""
from __future__ import annotations

from dataclasses import dataclass

KNOWN_ACTIONS = frozenset(
    {
        "EXECUTE_PAYMENT",
        "PAYMENT_DEFERRAL",
        "UNBLOCK_SIM",
        "REPLACE_SIM",
        "REACTIVATE_SIM",
        "TOP_UP",
        "CHANGE_PLAN",
        "ACTIVATE_ROAMING",
    }
)


@dataclass(frozen=True)
class Decision:
    """A candidate action ranked with a confidence and a short rationale."""

    action: str
    confidence: float
    rationale: str


def recommend(action_type: str, context: dict) -> Decision:
    """Return a candidate action + confidence for ``action_type`` given ``context``."""
    if action_type not in KNOWN_ACTIONS:
        return Decision(action_type, 0.2, "action not in the catalogue")
    confidence = 0.9
    rationale = "catalogued action with sufficient context"
    if not context.get("identity_verified", False):
        confidence -= 0.3
        rationale = "catalogued action but identity not yet verified"
    return Decision(action_type, round(confidence, 2), rationale)