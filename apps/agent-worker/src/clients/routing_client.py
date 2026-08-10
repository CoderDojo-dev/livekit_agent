"""Resolve a live human advisor for escalation (Blueprint section 6, Escalation context).

The destination is resolved DYNAMICALLY from the advisor registry, never hardcoded: the business
API atomically claims an available advisor whose skills match the escalating persona. A claim is a
reservation - if the transfer then fails, the advisor must be released so the next caller can
reach them.

When nobody is free this returns None and the caller is offered a callback. It never fabricates a
destination: transferring a caller to a number nobody answers is worse than telling them the truth.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvisorDestination:
    """A resolved human advisor and how to reach them."""

    advisor_id: str
    full_name: str
    skill_tag: str
    phone_e164: str | None = None
    sip_uri: str | None = None

    @property
    def transfer_uri(self) -> str:
        """The SIP REFER target: a sip: URI when configured, otherwise a tel: number."""
        if self.sip_uri:
            return self.sip_uri
        return f"tel:{self.phone_e164}" if self.phone_e164 else ""


class RoutingClient:
    """Claims and releases advisors from the registry."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        # The worker authenticates as a MACHINE, with the shared internal key business-api maps
        # to the conseiller rank - the exact rank these routes require. It no longer declares a
        # role: a caller asserting its own privilege was the P0-1 vulnerability.
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers=internal_headers()
        )

    async def resolve_available_advisor(self, skill_tag: str) -> AdvisorDestination | None:
        """Atomically claim an advisor for ``skill_tag``; None when none is free or reachable."""
        try:
            resp = await self._client.post(
                "/api/v1/advisors/claim", params={"skill_tag": skill_tag},
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            advisor = resp.json().get("advisor")
        except httpx.HTTPError as exc:
            logger.error("advisor claim failed for %r: %s", skill_tag, exc)
            return None
        if not advisor:
            return None

        destination = AdvisorDestination(
            advisor_id=advisor["id"], full_name=advisor.get("full_name", ""),
            skill_tag=skill_tag, phone_e164=advisor.get("phone_e164"),
            sip_uri=advisor.get("sip_uri"),
        )
        if not destination.transfer_uri:
            logger.error("advisor %s has no phone or SIP URI; releasing", destination.advisor_id)
            await self.release_advisor(destination.advisor_id)
            return None
        return destination

    async def release_advisor(self, advisor_id: str) -> None:
        """Return a claimed advisor to the pool (transfer failed, or the call ended)."""
        try:
            await self._client.post(
                f"/api/v1/advisors/{advisor_id}/release", headers=inject_trace_context()
            )
        except httpx.HTTPError as exc:
            logger.error("advisor release failed for %s: %s", advisor_id, exc)

    async def on_call_advisors(self) -> list[dict]:
        """Advisors to notify when a callback is scheduled. Empty list on failure."""
        try:
            resp = await self._client.get(
                "/api/v1/advisors/on-call", headers=inject_trace_context()
            )
            resp.raise_for_status()
            return resp.json().get("advisors", [])
        except httpx.HTTPError as exc:
            logger.error("on-call advisor lookup failed: %s", exc)
            return []

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_routing_client() -> RoutingClient:
    """Return a cached RoutingClient bound to the business API."""
    return RoutingClient(get_settings().business_api_url)