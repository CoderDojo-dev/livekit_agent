"""Offline tests for the retention cutoff math (no DB). The purge itself is integration-tested."""
from __future__ import annotations

from datetime import UTC, datetime

from business_api.jobs.retention import cutoff_date


def test_cutoff_date() -> None:
    now = datetime(2026, 6, 30, tzinfo=UTC)
    assert cutoff_date(90, now).isoformat() == "2026-04-01T00:00:00+00:00"
    assert cutoff_date(0, now) == now