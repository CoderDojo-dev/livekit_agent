"""Typed client to the context-service (Customer 360 + identity + read paths).

Each method degrades gracefully: a context-service outage returns None / [] / False rather
than crashing the call.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings
from session.customer_context import CustomerContext

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ContextClient:
    """Pre-fetch the caller snapshot, run identity checks, and read invoices/balance."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

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

    async def get_invoices(self, customer_id: str) -> list[dict]:
        """Return the caller's invoices (read-only, CDC section 5.1); [] on error."""
        try:
            resp = await self._client.get(f"/billing/{customer_id}/invoices")
            resp.raise_for_status()
            return resp.json().get("invoices", [])
        except httpx.HTTPError as exc:
            logger.warning("invoice read failed for %s: %s", customer_id, exc)
            return []

    async def get_balance(self, customer_id: str) -> dict | None:
        """Return the caller's prepaid balance, or None if absent/unavailable."""
        try:
            resp = await self._client.get(f"/balance/{customer_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("balance read failed for %s: %s", customer_id, exc)
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_context_client() -> ContextClient:
    """Return a cached ContextClient bound to the configured context-service URL."""
    return ContextClient(get_settings().context_service_url)