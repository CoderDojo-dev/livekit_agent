"""Offline tests: telemetry is a safe no-op when OTel/endpoint are absent (no raises)."""
from __future__ import annotations

from observability_kit import (
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


def test_configure_without_endpoint_is_noop(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    configure_tracer("agent-worker")  # must not raise


def test_recording_helpers_never_raise() -> None:
    # Not configured -> instruments empty -> these are no-ops, never raising.
    record_ttfa(0.42, language="fr")
    record_ttft(0.18, language="ar")
    incr_fallback("stt")
    incr_escalation("frustration")


def test_trace_helpers_never_raise() -> None:
    headers = inject_trace_context({"X-Custom": "val"})
    assert headers["X-Custom"] == "val"
    extracted = extract_trace_context(headers)
    assert extracted is None or isinstance(extracted, object)
    assert get_tracer() is None or isinstance(get_tracer(), object)
    with trace_span("test.span", attributes={"key": "val"}, headers=headers):
        pass


def test_trace_requests_noop() -> None:
    class DummyApp:
        def middleware(self, kind: str):
            def decorator(func):
                return func
            return decorator

    app = DummyApp()
    trace_requests(app, "test-service")  # must not raise
