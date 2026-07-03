"""OpenTelemetry tracer + meter + named instruments (Blueprint section 16).

Two design rules keep this safe to call from every service and the worker hot path:
  1. **Dependency-optional**: if the OTel SDK is not installed, everything degrades to a no-op.
  2. **Endpoint-gated**: telemetry is only wired when OTEL_EXPORTER_OTLP_ENDPOINT is set, so dev
     runs unchanged and nothing blocks on an absent collector.
Recording helpers never raise - metrics must never break a call.
"""
from __future__ import annotations

import logging
import os
from contextlib import suppress

logger = logging.getLogger(__name__)

try:  # OTel SDK is optional
    from opentelemetry import metrics as _otel_metrics
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:
    _OTEL_AVAILABLE = False

_METRIC_PREFIX = "telecom.agent"
_instruments: dict[str, object] = {}
_configured = False


def configure_tracer(service_name: str) -> None:
    """Wire the global tracer + meter for ``service_name`` if OTel is available and an endpoint is set."""
    global _configured
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or not _OTEL_AVAILABLE:
        logger.info("OTel disabled (endpoint=%s sdk=%s) for %s", bool(endpoint), _OTEL_AVAILABLE, service_name)
        return
    if _configured:
        return

    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    _otel_trace.set_tracer_provider(tracer_provider)

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
    _otel_metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    _build_instruments(service_name)
    _configured = True
    logger.info("OTel configured for %s -> %s", service_name, endpoint)


def _build_instruments(service_name: str) -> None:
    meter = _otel_metrics.get_meter(service_name)
    _instruments["ttfa"] = meter.create_histogram(
        f"{_METRIC_PREFIX}.ttfa.seconds", unit="s", description="Time to first audio"
    )
    _instruments["ttft"] = meter.create_histogram(
        f"{_METRIC_PREFIX}.ttft.seconds", unit="s", description="Time to first token (LLM)"
    )
    _instruments["fallback"] = meter.create_counter(
        f"{_METRIC_PREFIX}.fallback.activations", description="Provider fallback activations"
    )
    _instruments["escalation"] = meter.create_counter(
        f"{_METRIC_PREFIX}.escalations", description="Escalations to a manager/human"
    )


def record_ttfa(seconds: float, language: str | None = None) -> None:
    """Record a time-to-first-audio observation (no-op until configured)."""
    histogram = _instruments.get("ttfa")
    if histogram is not None:
        with suppress(Exception):
            histogram.record(seconds, {"language": language or "unknown"})


def record_ttft(seconds: float, language: str | None = None) -> None:
    """Record a time-to-first-token observation (no-op until configured)."""
    histogram = _instruments.get("ttft")
    if histogram is not None:
        with suppress(Exception):
            histogram.record(seconds, {"language": language or "unknown"})


def incr_fallback(component: str) -> None:
    """Count a provider fallback activation for ``component`` (stt/llm/tts)."""
    counter = _instruments.get("fallback")
    if counter is not None:
        with suppress(Exception):
            counter.add(1, {"component": component})


def incr_escalation(trigger: str) -> None:
    """Count an escalation, labelled by trigger."""
    counter = _instruments.get("escalation")
    if counter is not None:
        with suppress(Exception):
            counter.add(1, {"trigger": trigger})
