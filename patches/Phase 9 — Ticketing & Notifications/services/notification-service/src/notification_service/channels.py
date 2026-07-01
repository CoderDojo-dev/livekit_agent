"""Channel adapters. Phase 9 ships mock senders (log masked + record). Real SMS/WhatsApp/Email
providers (the notification ports) replace these without changing the service."""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)
_masker = PiiMasker()


class NotificationChannel(Protocol):
    """Sends a rendered message body to a destination and returns a provider reference."""

    name: str

    async def send(self, to: str, body: str) -> str: ...


class _MockChannel:
    name = "mock"

    async def send(self, to: str, body: str) -> str:
        reference = f"{self.name.upper()}-{uuid.uuid4().hex[:10].upper()}"
        logger.info("[%s] to=%s ref=%s body=%s", self.name, _masker.mask(to or ""), reference, body)
        return reference


class MockSmsChannel(_MockChannel):
    name = "sms"


class MockWhatsAppChannel(_MockChannel):
    name = "whatsapp"


class MockEmailChannel(_MockChannel):
    name = "email"


_CHANNELS: dict[str, NotificationChannel] = {
    "sms": MockSmsChannel(),
    "whatsapp": MockWhatsAppChannel(),
    "email": MockEmailChannel(),
}


def get_channel(name: str) -> NotificationChannel:
    """Return the channel adapter for ``name`` (defaults to SMS)."""
    return _CHANNELS.get(name, _CHANNELS["sms"])