"""Offline tests for Phase 6 production gates."""
from __future__ import annotations

import pytest

from knowledge_service.outbox_worker import retry_delay_seconds
from knowledge_service.quality_eval import percentile


def test_outbox_backoff_is_exponential_and_bounded() -> None:
    assert retry_delay_seconds(2.0, 1) == 2.0
    assert retry_delay_seconds(2.0, 2) == 4.0
    assert retry_delay_seconds(2.0, 5) == 32.0
    assert retry_delay_seconds(1000.0, 10) == 3600.0


def test_outbox_backoff_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        retry_delay_seconds(-1.0, 1)
    with pytest.raises(ValueError):
        retry_delay_seconds(1.0, 0)


def test_latency_percentile_uses_nearest_rank() -> None:
    samples = [float(value) for value in range(1, 101)]
    assert percentile(samples, 0.50) == 50.0
    assert percentile(samples, 0.95) == 95.0


def test_latency_percentile_requires_samples() -> None:
    with pytest.raises(ValueError):
        percentile([], 0.95)
