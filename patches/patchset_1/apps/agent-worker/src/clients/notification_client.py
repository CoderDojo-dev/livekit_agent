"""Typed client to the notification-service (worker-initiated written confirmations)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from service_auth import internal_headers

from config import get_settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """Send a localized written confirmation; degrades gracefully on error."""

    def __init__(self, base_url: str, timeout: float = 4.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def notify(
        self, customer_id: str, template: str, language: str, params: dict, channel: str = "sms"
    ) -> dict:
        """Send a confirmation; returns {'sent': bool, ...}. Never raises into the call."""
        try:
            resp = await self._client.post(
                "/notify",
                json={
                    "customer_id": customer_id,
                    "to": customer_id,
                    "channel": channel,
                    "template": template,
                    "language": language,
                    "params": params,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("notification send failed (%s): %s", template, exc)
            return {"sent": False}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_notification_client() -> NotificationClient:
    """Return a cached NotificationClient bound to the configured notification-service URL."""
    return NotificationClient(get_settings().notification_service_url)