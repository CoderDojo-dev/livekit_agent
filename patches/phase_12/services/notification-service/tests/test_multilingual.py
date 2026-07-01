"""Multilingual UAT (FR/AR/EN): every written confirmation renders in all three languages."""
from __future__ import annotations

from notification_service.templates import render

LANGUAGES = ("fr", "ar", "en")


def test_ticket_created_renders_in_all_languages() -> None:
    for lang in LANGUAGES:
        text = render("ticket_created", lang, {"ticket_id": "GLPI-00001"})
        assert text and "GLPI-00001" in text


def test_callback_scheduled_renders_in_all_languages() -> None:
    for lang in LANGUAGES:
        text = render("callback_scheduled", lang, {"when": "demain 10h"})
        assert text and "demain 10h" in text


def test_arabic_is_not_an_english_fallback() -> None:
    fr = render("ticket_created", "fr", {"ticket_id": "X"})
    ar = render("ticket_created", "ar", {"ticket_id": "X"})
    en = render("ticket_created", "en", {"ticket_id": "X"})
    assert ar not in (fr, en)  # genuinely localized, not silently falling back