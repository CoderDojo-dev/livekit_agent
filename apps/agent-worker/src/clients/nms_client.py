"""Typed client to the NMS/OSS network-status service (known outages by area).

Used by the technical persona to answer "is there a known incident in my area?" with real data
from oss.outages rather than an optimistic default. A service failure is reported honestly to the
tool (status="unavailable") so the agent can tell the caller the truth instead of claiming the
network is fine when we simply could not check.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


_KEYTERMS_CACHE: dict[str, list[str]] = {}


class NmsClient:
    """Read known network incidents for an area."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers=internal_headers()
        )

    async def get_network_status(self, area: str, language: str = "fr") -> dict:
        """Return {area, status, verified, outages[], ...}.

        On transport failure returns status="unavailable" with verified=False - never a
        fabricated "operational", which would tell a caller the network is fine when we
        never reached the NMS.
        """
        try:
            resp = await self._client.get(
                "/network-status",
                params={"area": area, "lang": language},
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("network status lookup failed for %r: %s", area, exc)
            return {
                "area": area,
                "status": "unavailable",
                "verified": False,
                "outages": [],
                "error": str(exc),
            }

    async def get_geo_keyterms(self, language: str = "fr") -> list[str]:
        """Noms de lieux a annoncer a la transcription. Un seul appel par processus.

        En cas d'echec on renvoie une liste vide : la transcription demarre sans
        indication, ce qui est degrade mais jamais bloquant.
        """
        if language in _KEYTERMS_CACHE:
            return _KEYTERMS_CACHE[language]
        try:
            response = await self._client.get(
                "/geo-keyterms",
                params={"lang": language},
                headers=internal_headers(),
            )
            response.raise_for_status()
            terms = response.json().get("keyterms") or []
        except Exception as exc:
            logger.warning(
                "geo keyterms indisponibles (%s) ; la transcription demarre "
                "sans noms de lieux",
                exc,
            )
            terms = []
        _KEYTERMS_CACHE[language] = terms
        return terms

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_nms_client() -> NmsClient:
    """Return a cached NmsClient bound to the configured NMS service URL."""
    return NmsClient(get_settings().nms_service_url)
