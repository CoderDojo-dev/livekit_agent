"""KPI math (Blueprint section 16.1) - pure, unit-testable."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Kpis:
    """Containment / escalation KPIs over the persisted conversation record."""

    total_sessions: int
    resolved: int
    escalated: int
    containment_rate: float
    escalation_rate: float
    avg_frustration: float


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def compute_kpis(total_sessions: int, resolved: int, escalated: int, avg_frustration: float) -> Kpis:
    """Build the KPI bundle from raw counts."""
    return Kpis(
        total_sessions=total_sessions,
        resolved=resolved,
        escalated=escalated,
        containment_rate=_ratio(resolved, total_sessions),
        escalation_rate=_ratio(escalated, total_sessions),
        avg_frustration=round(float(avg_frustration or 0), 2),
    )