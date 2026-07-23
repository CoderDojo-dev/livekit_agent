"""Typed client to the notification-service (worker-initiated written confirmations)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

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
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("notification send failed (%s): %s", template, exc)
            return {"sent": False}

    async def notify_advisor(
        self, channel: str, to: str, template: str, language: str, params: dict
    ) -> bool:
        """Send a message to an ADVISOR (not a customer), addressed explicitly.

        Advisors are not customers, so the notification-service cannot resolve their contact from
        a customer_id: the handle is passed directly via ``to``, which the service honours as an
        override. Returns whether it was actually sent - never assumed.
        """
        try:
            resp = await self._client.post(
                "/notify",
                json={
                    "customer_id": "", "to": to, "channel": channel,
                    "template": template, "language": language, "params": params,
                },
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            return bool(resp.json().get("sent"))
        except httpx.HTTPError as exc:
            logger.warning("advisor notification failed (%s -> %s): %s", template, channel, exc)
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_notification_client() -> NotificationClient:
    """Return a cached NotificationClient bound to the configured notification-service URL."""
    return NotificationClient(get_settings().notification_service_url)
