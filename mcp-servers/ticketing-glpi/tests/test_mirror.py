"""Offline tests for the ticket-mirror pure logic (no DB)."""
from __future__ import annotations

from ticketing_glpi.adapters.mirror import normalize_category, read_status


def test_normalize_category() -> None:
    assert normalize_category("network_complaint") == "network_complaint"
    assert normalize_category("billing") == "billing"
    assert normalize_category("weird") == "other"
    assert normalize_category(None) == "other"


def test_mirror_disabled_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert read_status("GLPI-00001") is None  # gated off -> mock fallback handles reads