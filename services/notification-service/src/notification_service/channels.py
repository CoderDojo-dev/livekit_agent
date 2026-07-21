"""Channel adapters (live-only). Twilio REST SMS/WhatsApp + stdlib SMTP email.
No mock fallback: unconfigured or failed channels raise ChannelUnavailable.
Every channel is independent — Twilio can be live while SMTP is not configured, and vice-versa.
"""
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


class ChannelUnavailable(Exception):
    """Raised when a channel is not configured or its provider rejects the send."""


class NotificationChannel(Protocol):
    name: str
    configured: bool

    async def send(self, to: str, body: str) -> str: ...


class TwilioChannel:
    """SMS/WhatsApp via the Twilio REST API (no SDK dependency)."""

    def __init__(self, name: str, from_number: str) -> None:
        self.name = name
        self._from = from_number
        self._sid = os.environ["TWILIO_ACCOUNT_SID"]
        self._token = os.environ["TWILIO_AUTH_TOKEN"]

    @property
    def configured(self) -> bool:
        return bool(self._sid and self._from)

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

    @property
    def configured(self) -> bool:
        return bool(self._host)

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


# ---------------- configuration / factory ----------------
def _twilio_creds() -> bool:
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))


def _sms_configured() -> bool:
    return bool(_twilio_creds() and os.getenv("TWILIO_SMS_FROM"))


def _whatsapp_configured() -> bool:
    return bool(_twilio_creds() and os.getenv("TWILIO_WHATSAPP_FROM"))


def _email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def channel_status() -> dict[str, dict]:
    """Return the configured status of every channel (does NOT test the provider)."""
    status: dict[str, dict] = {}
    for name, label in (("sms", "SMS (Twilio)"), ("whatsapp", "WhatsApp (Twilio)"), ("email", "Email (SMTP)")):
        try:
            ch = _build_channel(name)
            status[name] = {"label": label, "configured": ch.configured, "name": ch.name}
        except ChannelUnavailable:
            status[name] = {"label": label, "configured": False}
    return status


def _build_channel(name: str) -> NotificationChannel:
    """Build (but do NOT test) a live channel or raise ChannelUnavailable."""
    if name in ("sms", "whatsapp"):
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        if not sid:
            raise ChannelUnavailable("TWILIO_ACCOUNT_SID not set")
        from_field = "TWILIO_SMS_FROM" if name == "sms" else "TWILIO_WHATSAPP_FROM"
        from_number = os.getenv(from_field, "")
        ch = TwilioChannel(name, from_number)
        if not ch.configured:
            raise ChannelUnavailable(f"{from_field} not set")
        return ch
    if name == "email":
        host = os.getenv("SMTP_HOST")
        if not host:
            raise ChannelUnavailable("SMTP_HOST not set")
        ch = SmtpEmailChannel()
        if not ch.configured:
            raise ChannelUnavailable("SMTP not fully configured")
        return ch
    raise ChannelUnavailable(f"unknown channel {name!r}")


def get_channel(name: str) -> NotificationChannel:
    """Return a live channel adapter or raise ChannelUnavailable (no mock fallback)."""
    if name not in ("sms", "whatsapp", "email"):
        raise ChannelUnavailable(f"unknown channel {name!r}")
    return _build_channel(name)
