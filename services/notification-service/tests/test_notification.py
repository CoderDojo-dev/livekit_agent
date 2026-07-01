"""Offline tests for rendering + mock send (no network)."""
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


def test_notify_sends_and_records() -> None:
    service = NotificationService()
    resp = asyncio.run(
        service.notify(
            NotifyRequest(customer_id="TT-100021", template="ticket_created",
                          language="en", params={"ticket_id": "GLPI-00002"})
        )
    )
    assert resp.sent is True
    assert resp.reference
    assert len(service.sent) == 1