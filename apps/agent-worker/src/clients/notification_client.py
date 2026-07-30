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
                    # No "to": the notification-service resolves the handle from crm.customers
                    # for the requested channel. Sending customer_id as "to" made every message
                    # addressed to a UUID.
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

    async def notify_first_available(
        self, customer_id: str, template: str, language: str, params: dict,
        channels: tuple[str, ...] = ("whatsapp", "email", "sms"),
    ) -> dict:
        """Try each channel until one is actually sent; report the one that worked.

        A channel can fail for two very different reasons — not configured, or the provider
        refused — and both are recoverable by trying the next one. The result always says
        which channel carried the message, so the agent never claims more than what happened.
        """
        last: dict = {"sent": False}
        for channel in channels:
            last = await self.notify(customer_id, template, language, params, channel=channel)
            if last.get("sent"):
                last["channel"] = channel
                return last
        return last

    async def notify_all_available(
        self,
        customer_id: str,
        template: str,
        language: str,
        params: dict,
        channels: tuple[str, ...] = ("whatsapp", "email"),
        fallback: str = "sms",
    ) -> list[str]:
        """Send the same confirmation on every channel the customer can be reached on.

        A booked callback is a commitment, so the written trace should exist wherever the
        caller will look for it. Channels are independent: WhatsApp failing must not suppress
        the email. Returns the channels that actually went out.

        ``fallback`` is only tried when every primary channel failed, so a customer with no
        WhatsApp and no email still gets an SMS rather than silence.
        """
        delivered: list[str] = []
        for channel in channels:
            try:
                result = await self.notify(customer_id, template, language, params, channel=channel)
            except Exception as exc:  # one dead channel must never hide the others
                logger.warning("notify %s failed: %s", channel, exc)
                continue
            if result.get("sent"):
                delivered.append(channel)
            else:
                logger.info("notify %s not delivered: %s", channel, result.get("reason", ""))

        if not delivered and fallback:
            result = await self.notify(customer_id, template, language, params, channel=fallback)
            if result.get("sent"):
                delivered.append(fallback)
        return delivered

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_notification_client() -> NotificationClient:
    """Return a cached NotificationClient bound to the configured notification-service URL."""
    return NotificationClient(get_settings().notification_service_url)
