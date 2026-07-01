"""Typed client to the context-service (Customer 360 + identity check).

Each method degrades gracefully: a context-service outage returns None / False rather than
crashing the call (the caller flow then proceeds unverified or unpersonalized).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from config import get_settings
from session.customer_context import CustomerContext

logger = logging.getLogger(__name__)


class ContextClient:
    """Pre-fetch the caller snapshot and run the server-side identity check."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get_snapshot(self, msisdn: str) -> CustomerContext | None:
        """Return the caller's CustomerContext, or None if unknown/unavailable."""
        try:
            resp = await self._client.get(f"/context/{msisdn}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return CustomerContext.from_snapshot(resp.json())
        except httpx.HTTPError as exc:
            logger.warning("context prefetch failed for %s: %s", msisdn, exc)
            return None

    async def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Return True iff the step-up answer matches; False on mismatch or service error."""
        try:
            resp = await self._client.post(
                "/verify-identity",
                json={"customer_id": customer_id, "answer": answer},
            )
            resp.raise_for_status()
            return bool(resp.json().get("verified"))
        except httpx.HTTPError as exc:
            logger.warning("identity verification call failed for %s: %s", customer_id, exc)
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_context_client() -> ContextClient:
    """Return a cached ContextClient bound to the configured context-service URL."""
    return ContextClient(get_settings().context_service_url)