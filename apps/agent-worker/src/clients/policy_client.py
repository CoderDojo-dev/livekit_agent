"""Typed client to the policy-service: the single mandatory checkpoint (never bypassable)."""
from __future__ import annotations

import logging
import time
from functools import lru_cache

import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


class PolicyClient:
    """Call Policy before any execution and any outbound response.

    Fail-closed: if Policy is unreachable, the verdict defaults to ESCALATE (never AUTHORIZED),
    so an outage can never silently authorize a sensitive action.
    """

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._timeout = timeout
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def evaluate_action(self, context: dict) -> dict:
        """Return the verdict dict for an action; ESCALATE on service error (fail-closed)."""
        started = time.perf_counter()
        try:
            resp = await self._client.post("/evaluate-action", json=context, headers=inject_trace_context())
            resp.raise_for_status()
            elapsed = time.perf_counter() - started
            # A slow checkpoint is a future fail-closed escalation, so warn before it becomes one.
            # This call writes a verdict row AND a hash-chained audit link, so its cost grew when
            # persistence started working; the budget must be arbitrated on measurements.
            if elapsed > self._timeout / 2:
                logger.warning(
                    "policy_slow evaluate-action took %.3fs of a %.1fs budget", elapsed, self._timeout
                )
            return resp.json()
        except httpx.HTTPError as exc:
            # A timeout, a 500 and a refused connection all fail closed to the same verdict, but
            # they are three different defects: too slow, broken, or down. Name the class so the
            # logs can be counted per cause - the verdict contract itself is unchanged.
            elapsed = time.perf_counter() - started
            cause = (
                "timeout" if isinstance(exc, httpx.TimeoutException)
                else "http_status" if isinstance(exc, httpx.HTTPStatusError)
                else "transport"
            )
            logger.error(
                "policy_fail_closed evaluate-action cause=%s elapsed=%.3fs budget=%.1fs; ESCALATE: %s",
                cause, elapsed, self._timeout, exc,
            )
            return {"verdict": "escalate", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def evaluate_response(self, session_id: str, text: str) -> dict:
        """Guardrail an outbound response; REFUSED on service error (fail-closed)."""
        started = time.perf_counter()
        try:
            resp = await self._client.post(
                "/evaluate-response", json={"session_id": session_id, "text": text}, headers=inject_trace_context()
            )
            resp.raise_for_status()
            elapsed = time.perf_counter() - started
            # A slow guardrail is a future fail-closed refusal, so warn before it becomes one.
            # This call writes a verdict row AND a hash-chained audit link, so its cost grew when
            # persistence started working; the budget must be arbitrated on measurements.
            if elapsed > self._timeout / 2:
                logger.warning(
                    "policy_slow evaluate-response took %.3fs of a %.1fs budget", elapsed, self._timeout
                )
            return resp.json()
        except httpx.HTTPError as exc:
            # A timeout, a 500 and a refused connection all fail closed to the same verdict, but
            # they are three different defects: too slow, broken, or down. Name the class so the
            # logs can be counted per cause - the verdict contract itself is unchanged.
            elapsed = time.perf_counter() - started
            cause = (
                "timeout" if isinstance(exc, httpx.TimeoutException)
                else "http_status" if isinstance(exc, httpx.HTTPStatusError)
                else "transport"
            )
            logger.error(
                "policy_fail_closed evaluate-response cause=%s elapsed=%.3fs budget=%.1fs; REFUSED: %s",
                cause, elapsed, self._timeout, exc,
            )
            return {"verdict": "refused", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_policy_client() -> PolicyClient:
    """Return a cached PolicyClient bound to the configured policy-service URL."""
    return PolicyClient(get_settings().policy_service_url)
