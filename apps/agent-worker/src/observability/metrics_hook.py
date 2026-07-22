"""TTFA/TTFT + usage metrics hook (cookbook section 13, Blueprint section 16).

Attaches non-blocking listeners to an AgentSession: per-component metrics are logged via the SDK
helper, time-to-first-audio is derived from the end-of-utterance timestamp, and TTFA/TTFT are
exported to OpenTelemetry (no-op until a collector is configured). Adds zero latency to the reply.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics

from observability_kit import record_ttfa, record_ttft

logger = logging.getLogger(__name__)


def attach_metrics(session):
    """Wire usage collection + TTFA/TTFT logging/export onto ``session``; return a shutdown callback."""
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: dict[str, Any] = {"value": None}

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metric = ev.metrics
        metric_type = getattr(metric, "type", None)
        if metric_type == "eou_metrics":
            last_eou_metrics["value"] = metric
        if metric_type == "llm_metrics":
            ttft = getattr(metric, "ttft", None)
            if ttft:
                record_ttft(float(ttft))  # export time-to-first-token
        metrics.log_metrics(metric)
        usage_collector.collect(metric)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        eou = last_eou_metrics["value"]
        if ev.new_state == "speaking" and eou is not None:
            try:
                ttfa = time.time() - eou.timestamp  # EOUMetrics.timestamp is confirmed
                logger.info("time_to_first_audio_seconds=%.3f", ttfa)
                record_ttfa(ttfa)  # export time-to-first-audio
            except Exception as exc:
                logger.debug("ttfa computation skipped: %s", exc)

    async def log_usage() -> None:
        logger.info("usage_summary=%s", usage_collector.get_summary())

    return log_usage