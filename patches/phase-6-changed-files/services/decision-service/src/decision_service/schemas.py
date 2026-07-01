"""Wire DTOs for the decision-service."""
from __future__ import annotations

from pydantic import BaseModel


class DecisionRequest(BaseModel):
    """A candidate-action ranking request."""

    action_type: str
    context: dict = {}


class DecisionResponse(BaseModel):
    """The ranked candidate action with confidence."""

    action: str
    confidence: float
    rationale: str