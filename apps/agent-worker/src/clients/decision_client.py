"""Typed client to the decision-service (candidate-action ranking)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


class DecisionClient:
    """Ask the Decision context to rank a candidate action before Policy."""

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def recommend(self, action_type: str, context: dict) -> dict:
        """Return {action, confidence, rationale}; low confidence on service error."""
        try:
            resp = await self._client.post(
                "/recommend", json={"action_type": action_type, "context": context}, headers=inject_trace_context()
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("decision recommend failed; low confidence: %s", exc)
            return {"action": action_type, "confidence": 0.0, "rationale": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_decision_client() -> DecisionClient:
    """Return a cached DecisionClient bound to the configured decision-service URL."""
    return DecisionClient(get_settings().decision_service_url)
