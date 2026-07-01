"""Port to the Execution context (CDC section 4.7)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import Action


class ExecutionPort(ABC):
    """Dispatch an authorized, idempotent action to the right adapter."""

    @abstractmethod
    async def execute(self, action: Action, context: dict[str, Any]) -> Action:
        """Execute ``action`` idempotently and return it with status + reference."""