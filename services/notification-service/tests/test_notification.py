"""Offline tests for rendering + the live-only honest-failure contract (no network, no mocks)."""
from __future__ import annotations

import asyncio

from notification_service.schemas import NotifyRequest
from notification_service.service import NotificationService
from notification_service.templates import render


def test_renders_localized_template() -> None:
    text = render("ticket_created", "fr", {"ticket_id": "GLPI-00001"})
    assert "GLPI-00001" in text
    assert "ticket" in text.lower()


def test_unknown_language_falls_back_to_english() -> None:
    text = render("callback_scheduled", "de", {"when": "tomorrow 10am"})
    assert "tomorrow 10am" in text


def test_notify_without_live_channel_reports_honest_failure(monkeypatch) -> None:
    """Live-only, no stub/mock: with no provider configured the service must NOT fake a send.

    It renders, attempts the real channel, and returns an honest ``sent=False`` with a failed record -
    exactly the platform's "never claim a send that did not happen" guarantee. ``to`` is the documented
    server-side override (schemas.py), which keeps this offline (no DB lookup) while still exercising
    the real render -> channel -> record pipeline. The ``delenv`` calls only establish the "no live
    infra" environment deterministically; they configure the environment, they do not mock any code.
    """
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM",
                "TWILIO_SMS_FROM", "SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)

    service = NotificationService()
    resp = asyncio.run(
        service.notify(
            NotifyRequest(customer_id="TT-100021", to="+21620155320", channel="whatsapp",
                          template="ticket_created", language="fr",
                          params={"ticket_id": "GLPI-00002"})
        )
    )

    assert resp.sent is False                 # never a fake success
    assert resp.reference == ""               # nothing was sent, so no provider reference
    assert resp.reason                        # a real reason (channel not configured)
    assert len(service.sent) == 1             # the attempt is still recorded...
    assert service.sent[0]["sent"] is False   # ...as a failure, honestly