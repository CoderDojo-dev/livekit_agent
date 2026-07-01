"""Capture TTFA/TTFT and fallback activations. Phase 3/11 wire the metric stream."""
from __future__ import annotations


class MetricsHooks:
    """Subscribe to the session metrics stream (Phase 3 wires UsageCollector)."""

    def attach(self, session) -> None:
        raise NotImplementedError("wired in Phase 3 / Phase 11 (Observability)")