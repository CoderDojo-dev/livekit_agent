"""Typed client to the callback queue (slot offer + booking).

Slots come from the business API, never from the worker: availability depends on the advisor
registry and on what other callers have already booked, which only the database knows.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context

logger = logging.getLogger(__name__)


class CallbackClient:
    """Reads free slots and books one. Failures degrade to 'no slot', never to a fake one."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers={"X-Role": "conseiller"}
        )

    async def free_slots(self, days: int = 2, limit: int = 6) -> list[dict]:
        """Bookable slots, soonest first; empty list on any failure."""
        try:
            resp = await self._client.get(
                "/api/v1/callbacks/slots", params={"days": days, "limit": limit},
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            return resp.json().get("slots", [])
        except httpx.HTTPError as exc:
            logger.error("callback slot lookup failed: %s", exc)
            return []

    async def reserve(self, slot_start: str, **payload) -> dict | None:
        """Book one slot; None when it is gone or the API is unreachable."""
        body = {"slot_start": slot_start, **payload}
        try:
            resp = await self._client.post(
                "/api/v1/callbacks/reserve", json=body, headers=inject_trace_context()
            )
            if resp.status_code == 409:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("callback reservation failed: %s", exc)
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_callback_client() -> CallbackClient:
    """Return a cached CallbackClient bound to the business API."""
    return CallbackClient(get_settings().business_api_url)
