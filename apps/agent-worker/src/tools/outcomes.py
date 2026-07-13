"""Standard tool-outcome contract (review note 5c).

Every sensitive tool returns one of these shapes - never a raw exception or a bare string - so
the worker/LLM can always map a result to a clear spoken explanation instead of a generic
"I encountered an error". The 'message' is English guidance for the LLM to render in-language.
"""
from __future__ import annotations

AUTHORIZED = "authorized"
EXECUTED = "executed"
REFUSED = "refused"
ESCALATE = "escalate"
FAILED = "failed"


def refused(rule_id: str, reason: str) -> dict:
    """A policy refusal the caller should hear explained (not retried silently)."""
    return {
        "outcome": REFUSED,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This request cannot be completed because: {reason}. Offer an alternative if one exists.",
    }


def escalate(rule_id: str, reason: str) -> dict:
    """An escalation: explain briefly and hand off to a human via escalate_to_manager."""
    return {
        "outcome": ESCALATE,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This needs a human specialist ({reason}). Explain briefly, then call escalate_to_manager.",
    }


def executed(action_type: str, reference: str, replay: bool = False) -> dict:
    """A successful, idempotent execution carrying a reference the caller can be given."""
    return {
        "outcome": EXECUTED,
        "action_type": action_type,
        "reference": reference,
        "replay": replay,
        "message": f"The {action_type} was completed. Confirmation reference: {reference}.",
    }


def failed(reason: str, message: str | None = None) -> dict:
    """A hard execution failure: apologize and offer escalation, never claim success."""
    return {
        "outcome": FAILED,
        "reason": reason,
        "message": message or "The action could not be completed right now. Apologize briefly and offer to escalate.",
    }