"""Typed client to the policy-service: the single mandatory checkpoint (never bypassable)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from service_auth import internal_headers

from config import get_settings

logger = logging.getLogger(__name__)


class PolicyClient:
    """Call Policy before any execution and any outbound response.

    Fail-closed: if Policy is unreachable, the verdict defaults to ESCALATE (never AUTHORIZED),
    so an outage can never silently authorize a sensitive action.
    """

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def evaluate_action(self, context: dict) -> dict:
        """Return the verdict dict for an action; ESCALATE on service error (fail-closed)."""
        try:
            resp = await self._client.post("/evaluate-action", json=context)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("policy evaluate-action failed; failing closed to ESCALATE: %s", exc)
            return {"verdict": "escalate", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def evaluate_response(self, session_id: str, text: str) -> dict:
        """Guardrail an outbound response; REFUSED on service error (fail-closed)."""
        try:
            resp = await self._client.post(
                "/evaluate-response", json={"session_id": session_id, "text": text}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("policy evaluate-response failed; failing closed to REFUSED: %s", exc)
            return {"verdict": "refused", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_policy_client() -> PolicyClient:
    """Return a cached PolicyClient bound to the configured policy-service URL."""
    return PolicyClient(get_settings().policy_service_url)