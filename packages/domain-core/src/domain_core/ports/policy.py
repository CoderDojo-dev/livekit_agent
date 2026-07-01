"""Port to the deterministic Policy & Guardrail engine (CDC section 4.6)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import PolicyVerdict


class PolicyPort(ABC):
    """The single mandatory checkpoint before any execution and any outbound response."""

    @abstractmethod
    async def evaluate_action(self, action: str, context: dict[str, Any]) -> PolicyVerdict:
        """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification for an action."""

    @abstractmethod
    async def evaluate_response(self, text: str, context: dict[str, Any]) -> PolicyVerdict:
        """Guardrail an outbound response (PII / promises / amounts)."""