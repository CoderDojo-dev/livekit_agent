"""Port to the hash-chained audit ledger (CDC sections 8.4 / 9.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import AuditEntry


class AuditPort(ABC):
    """Append an immutable, hash-chained audit entry."""

    @abstractmethod
    async def append(self, payload: dict[str, Any]) -> AuditEntry:
        """Append ``payload`` to the ledger and return the chained entry."""