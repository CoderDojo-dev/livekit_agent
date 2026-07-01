"""Wire DTOs for the policy-service."""
from __future__ import annotations

from pydantic import BaseModel


class PolicyContext(BaseModel):
    """Everything the deterministic engine needs to judge an action. English-only payload."""

    session_id: str = "unknown"
    action_type: str
    is_vip: bool = False
    fraud_suspected: bool = False
    frustration: bool = False
    identity_verified: bool = False
    clarification_attempts: int = 0
    identity_attempts: int = 0
    amount: float | None = None
    requested_days: int | None = None
    account_age_days: int = 0
    deferrals_this_year: int = 0
    unpaid_amount: float = 0.0
    payment_confirmed: bool = False


class EvaluateResponseRequest(BaseModel):
    """Outbound guardrail input (CDC section 10.3)."""

    session_id: str = "unknown"
    text: str


class VerdictResponse(BaseModel):
    """The three-way verdict plus rule-id and human-readable justification (ADR section 5.5)."""

    verdict: str  # "authorized" | "refused" | "escalate"
    rule_id: str
    justification: str