"""Port to network supervision (NMS) (Blueprint section 7.5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NmsPort(ABC):
    """Query known network incidents and remotely reset services."""

    @abstractmethod
    async def get_network_status(self, area: str) -> dict[str, Any]:
        """Return any known incident for ``area`` and an ETA."""