"""Wire DTOs for the execution-service."""
from __future__ import annotations

from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    """An AUTHORIZED action to dispatch. The idempotency_key makes a retry safe (spec section 12.2)."""

    idempotency_key: str
    action_type: str
    session_id: str = "unknown"
    policy_verdict_id: str            # the verdict that authorized this action (FK, required)
    customer_id: str | None = None
    subscription_id: str | None = None
    target_domain: str | None = None  # derived from action_type if omitted
    payload: dict = {}


class ExecuteResponse(BaseModel):
    """The result of dispatch; ``replay`` is True when a duplicate key returned the prior result."""

    status: str
    reference: str
    action_type: str
    replay: bool = False