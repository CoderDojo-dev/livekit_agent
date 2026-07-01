"""Offline tests: telemetry is a safe no-op when OTel/endpoint are absent (no raises)."""
from __future__ import annotations

from observability_kit import configure_tracer, incr_escalation, incr_fallback, record_ttfa, record_ttft


def test_configure_without_endpoint_is_noop(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    configure_tracer("agent-worker")  # must not raise


def test_recording_helpers_never_raise() -> None:
    # Not configured -> instruments empty -> these are no-ops, never raising.
    record_ttfa(0.42, language="fr")
    record_ttft(0.18, language="ar")
    incr_fallback("stt")
    incr_escalation("frustration")