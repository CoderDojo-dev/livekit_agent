"""Wire DTOs for the execution-service."""
from __future__ import annotations

from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    """An AUTHORIZED action to dispatch. The idempotency_key makes a retry safe (CDC 4.7)."""

    idempotency_key: str
    action_type: str
    session_id: str = "unknown"
    payload: dict = {}


class ExecuteResponse(BaseModel):
    """The result of dispatch; ``replay`` is True when a duplicate key returned the prior result."""

    status: str  # "executed"
    reference: str
    action_type: str
    replay: bool = False