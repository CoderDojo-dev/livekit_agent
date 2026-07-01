"""Offline tests for the KPI math (no DB)."""
from __future__ import annotations

from business_api.kpis import compute_kpis


def test_compute_kpis() -> None:
    k = compute_kpis(total_sessions=10, resolved=7, escalated=2, avg_frustration=0.456)
    assert k.containment_rate == 0.7
    assert k.escalation_rate == 0.2
    assert k.avg_frustration == 0.46


def test_compute_kpis_no_sessions() -> None:
    k = compute_kpis(total_sessions=0, resolved=0, escalated=0, avg_frustration=0)
    assert k.containment_rate == 0.0
    assert k.escalation_rate == 0.0