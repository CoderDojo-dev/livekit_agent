"""Port to the Decision context (CDC section 4.5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import Decision


class DecisionPort(ABC):
    """Rank a candidate action with a confidence value."""

    @abstractmethod
    async def recommend(self, intent: str, context: dict[str, Any]) -> Decision:
        """Return the best candidate action + confidence for ``intent``."""