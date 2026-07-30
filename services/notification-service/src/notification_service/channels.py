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
        self._sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self._token = os.getenv("TWILIO_AUTH_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self._sid and self._token and self._from)

    @staticmethod
    def _address(number: str, prefix: str) -> str:
        """Twilio rejects a doubled channel prefix; the console shows numbers already prefixed."""
        clean = (number or "").strip()
        if clean.startswith("whatsapp:"):
            clean = clean[len("whatsapp:"):]
        return f"{prefix}{clean}"

    async def send(self, to: str, body: str) -> str:
        prefix = "whatsapp:" if self.name == "whatsapp" else ""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url, auth=(self._sid, self._token),
                data={"From": self._address(self._from, prefix),
                      "To": self._address(to, prefix), "Body": body},
            )
            resp.raise_for_status()
            return resp.json().get("sid", "")


class SmtpEmailChannel:
    """Email via SMTP (stdlib, run off the event loop)."""

    name = "email"

    def __init__(self) -> None:
        self._host = os.getenv("SMTP_HOST", "")
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
        with smtplib.SMTP(self._host, self._port, timeout=10) as server:
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
        ch: NotificationChannel = TwilioChannel(name, from_number)  # type: ignore[assignment]
        if not ch.configured:
            raise ChannelUnavailable(f"{from_field} not set")
        return ch
    if name == "email":
        host = os.getenv("SMTP_HOST")
        if not host:
            raise ChannelUnavailable("SMTP_HOST not set")
        ch2 = SmtpEmailChannel()
        if not ch2.configured:
            raise ChannelUnavailable("SMTP not fully configured")
        return ch2  # type: ignore[return-value]
    raise ChannelUnavailable(f"unknown channel {name!r}")


def get_channel(name: str) -> NotificationChannel:
    """Return a live channel adapter or raise ChannelUnavailable (no mock fallback)."""
    if name not in ("sms", "whatsapp", "email"):
        raise ChannelUnavailable(f"unknown channel {name!r}")
    return _build_channel(name)


async def verify_credentials() -> dict[str, dict]:
    """Actually ask each provider whether our credentials work.

    channel_status() only reports whether variables are set, which is why a wrong auth token
    looked healthy right up to the first live call.
    """
    report: dict[str, dict] = {}

    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if sid and token:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, auth=(sid, token))
            report["twilio"] = {
                "ok": resp.status_code == 200,
                "status": resp.status_code,
                "account": resp.json().get("friendly_name", "") if resp.status_code == 200 else "",
            }
        except Exception as exc:
            report["twilio"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        report["twilio"] = {"ok": False, "error": "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set"}

    host = os.getenv("SMTP_HOST", "")
    if host:
        def _probe() -> dict:
            with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as server:
                server.starttls()
                user = os.getenv("SMTP_USER", "")
                if user:
                    server.login(user, os.getenv("SMTP_PASSWORD", ""))
            return {"ok": True}
        try:
            report["smtp"] = await asyncio.to_thread(_probe)
        except Exception as exc:
            report["smtp"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        report["smtp"] = {"ok": False, "error": "SMTP_HOST not set"}

    return report
