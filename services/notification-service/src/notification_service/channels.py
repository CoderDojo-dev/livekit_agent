"""Channel adapters (report #5): mock by default; real SMS/WhatsApp (Twilio REST) + Email (SMTP)
when CONNECTOR_MODE=live and the provider is configured. Falls back to mock if a provider's
credentials are missing, so a half-configured env degrades safely."""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Protocol

import httpx

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)
_masker = PiiMasker()


class NotificationChannel(Protocol):
    name: str

    async def send(self, to: str, body: str) -> str: ...


# ---------------- mock ----------------
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


# ---------------- live ----------------
class TwilioChannel:
    """SMS/WhatsApp via the Twilio REST API (no SDK dependency)."""

    def __init__(self, name: str, from_number: str) -> None:
        self.name = name
        self._from = from_number
        self._sid = os.environ["TWILIO_ACCOUNT_SID"]
        self._token = os.environ["TWILIO_AUTH_TOKEN"]

    async def send(self, to: str, body: str) -> str:
        prefix = "whatsapp:" if self.name == "whatsapp" else ""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url, auth=(self._sid, self._token),
                data={"From": f"{prefix}{self._from}", "To": f"{prefix}{to}", "Body": body},
            )
            resp.raise_for_status()
            return resp.json().get("sid", "")


class SmtpEmailChannel:
    """Email via SMTP (stdlib, run off the event loop)."""

    name = "email"

    def __init__(self) -> None:
        self._host = os.environ["SMTP_HOST"]
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._user = os.getenv("SMTP_USER", "")
        self._password = os.getenv("SMTP_PASSWORD", "")
        self._from = os.getenv("EMAIL_FROM", self._user)

    def _send_sync(self, to: str, body: str) -> str:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to
        message["Subject"] = "Tunisie Telecom"
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port) as server:
            server.starttls()
            if self._user:
                server.login(self._user, self._password)
            server.send_message(message)
        return f"EMAIL-{uuid.uuid4().hex[:10].upper()}"

    async def send(self, to: str, body: str) -> str:
        return await asyncio.to_thread(self._send_sync, to, body)


_MOCKS: dict[str, NotificationChannel] = {
    "sms": MockSmsChannel(), "whatsapp": MockWhatsAppChannel(), "email": MockEmailChannel(),
}


def _live_channel(name: str) -> NotificationChannel | None:
    """Build a live channel if its provider is configured; else None (→ mock fallback)."""
    try:
        if name == "sms" and os.getenv("TWILIO_ACCOUNT_SID"):
            return TwilioChannel("sms", os.getenv("TWILIO_SMS_FROM", ""))
        if name == "whatsapp" and os.getenv("TWILIO_ACCOUNT_SID"):
            return TwilioChannel("whatsapp", os.getenv("TWILIO_WHATSAPP_FROM", ""))
        if name == "email" and os.getenv("SMTP_HOST"):
            return SmtpEmailChannel()
    except Exception as exc:
        logger.warning("live channel %s unavailable (%s); using mock", name, exc)
    return None


def get_channel(name: str) -> NotificationChannel:
    """Return the channel adapter for ``name`` (live when configured, else mock; defaults to SMS)."""
    name = name if name in _MOCKS else "sms"
    if os.getenv("CONNECTOR_MODE", "mock").lower() == "live":
        live = _live_channel(name)
        if live is not None:
            return live
    return _MOCKS[name]