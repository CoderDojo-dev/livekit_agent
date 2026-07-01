"""Resolve a live human advisor for escalation (Blueprint section 6, Escalation context).

The destination is resolved DYNAMICALLY by skill, never hardcoded. The pilot has no live
advisor-routing system, so this returns None and escalations fall back to a scheduled
callback. Wire to the real routing service (or an availability API) in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AdvisorDestination:
    """A resolved human-advisor SIP endpoint."""

    participant_identity: str
    sip_uri: str
    skill_tag: str


class RoutingClient:
    """Resolves an available advisor by skill tag."""

    async def resolve_available_advisor(self, skill_tag: str) -> AdvisorDestination | None:
        """Return an available advisor for ``skill_tag``, or None if none is free."""
        # No live advisor-routing system in the pilot -> always None (callback fallback).
        return None


@lru_cache
def get_routing_client() -> RoutingClient:
    """Return a cached RoutingClient."""
    return RoutingClient()