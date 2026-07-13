"""Shared OpenTelemetry setup + the conversational-quality metric instruments (Blueprint section 16)."""
from observability_kit.telemetry import (
    configure_tracer,
    extract_trace_context,
    get_tracer,
    incr_escalation,
    incr_fallback,
    inject_trace_context,
    record_ttfa,
    record_ttft,
    trace_requests,
    trace_span,
)

__all__ = [
    "configure_tracer",
    "extract_trace_context",
    "get_tracer",
    "incr_escalation",
    "incr_fallback",
    "inject_trace_context",
    "record_ttfa",
    "record_ttft",
    "trace_requests",
    "trace_span",
]
