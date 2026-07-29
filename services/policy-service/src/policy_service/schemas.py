"""Wire DTOs for the policy-service."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PolicyContext(BaseModel):
    """Everything the deterministic engine needs to judge an action. English-only payload."""

    session_id: str = "unknown"
    customer_id: str | None = None
    subscription_id: str | None = None
    action_type: str
    is_vip: bool = False
    fraud_suspected: bool = False
    frustration: bool = False
    identity_verified: bool = False
    verified_customer_id: str | None = None
    identity_expires_at: datetime | None = None
    clarification_attempts: int = 0
    identity_attempts: int = 0
    amount: float | None = None
    requested_days: int | None = None
    account_age_days: int = 0
    deferrals_this_year: int | None = None
    unpaid_amount: float = 0.0
    plan_code: str | None = None
    enable: bool | None = None
    payment_confirmed: bool = False


class EvaluateResponseRequest(BaseModel):
    """Outbound guardrail input (CDC section 10.3)."""

    session_id: str = "unknown"
    text: str


class VerdictResponse(BaseModel):
    """The three-way verdict + rule-id + justification + the persisted verdict id (spec section 12.1)."""

    verdict: str  # "authorized" | "refused" | "escalate"
    rule_id: str
    justification: str
    verdict_id: str | None = None