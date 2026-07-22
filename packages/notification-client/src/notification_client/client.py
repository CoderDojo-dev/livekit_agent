"""NotificationPort implementation (report #11): posts to the notification-service over HTTP.

Replaces the log-only scaffold. Fault-tolerant: a delivery problem is logged, not raised, so a
notification never breaks the caller's flow.
"""
from __future__ import annotations

import logging
import os

import httpx

from domain_core.ports.notification import NotificationPort

logger = logging.getLogger(__name__)


class ChannelStrategyNotifier(NotificationPort):
    """Dispatch a localized confirmation through the notification-service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self._base_url = base_url or os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")
        self._timeout = timeout

    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        payload = {
            "customer_id": data.get("customer_id", to),
            "to": to,
            "channel": channel,
            "template": template,
            "language": data.get("language", "fr"),
            "params": data.get("params", data),
        }
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:  # type: ignore[arg-type]
                resp = await client.post("/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("notification dispatch failed (channel=%s template=%s): %s", channel, template, exc)