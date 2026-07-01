"""TTFA/TTFT + usage metrics hook (cookbook section 13, Blueprint section 16).

Attaches non-blocking listeners to an AgentSession: per-component metrics are logged via
the SDK helper, a usage summary is emitted at shutdown, and time-to-first-audio is derived
from the end-of-utterance timestamp. Adds zero latency to the spoken reply.
"""
from __future__ import annotations

import logging
import time

from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics

logger = logging.getLogger(__name__)


def attach_metrics(session):
    """Wire usage collection + TTFA logging onto ``session``; return an async shutdown callback."""
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: dict[str, object] = {"value": None}

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        if getattr(ev.metrics, "type", None) == "eou_metrics":
            last_eou_metrics["value"] = ev.metrics
        metrics.log_metrics(ev.metrics)  # logs TTFT for LLM, durations for STT/TTS
        usage_collector.collect(ev.metrics)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        eou = last_eou_metrics["value"]
        if ev.new_state == "speaking" and eou is not None:
            try:
                ttfa = time.time() - eou.timestamp  # EOUMetrics.timestamp is confirmed
                logger.info("time_to_first_audio_seconds=%.3f", ttfa)
            except Exception as exc:  # noqa: BLE001 - never let metrics break the call
                logger.debug("ttfa computation skipped: %s", exc)

    async def log_usage() -> None:
        logger.info("usage_summary=%s", usage_collector.get_summary())

    return log_usage