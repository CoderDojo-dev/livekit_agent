"""Port to the Notification context (Blueprint section 7.7)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationPort(ABC):
    """Send receipts/confirmations over SMS/WhatsApp/Email."""

    @abstractmethod
    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        """Send a templated notification."""