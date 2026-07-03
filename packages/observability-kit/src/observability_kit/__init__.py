"""Shared OpenTelemetry setup + the conversational-quality metric instruments (Blueprint section 16)."""
from observability_kit.telemetry import (
    configure_tracer,
    incr_escalation,
    incr_fallback,
    record_ttfa,
    record_ttft,
)

__all__ = [
    "configure_tracer",
    "incr_escalation",
    "incr_fallback",
    "record_ttfa",
    "record_ttft",
]