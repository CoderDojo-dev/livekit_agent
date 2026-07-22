"""Typed client to the execution-service. Returns a standard outcome (executed / failed)."""
from __future__ import annotations

import logging
from contextlib import suppress
from functools import lru_cache

import httpx
from config import get_settings
from tools import outcomes

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ExecutionClient:
    """Dispatch an AUTHORIZED action idempotently, carrying the authorizing verdict id."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def execute(
        self,
        idempotency_key: str,
        action_type: str,
        session_id: str,
        payload: dict,
        policy_verdict_id: str,
        customer_id: str | None = None,
        subscription_id: str | None = None,
    ) -> dict:
        """Execute the action; return an 'executed' or 'failed' outcome (never raises)."""
        try:
            resp = await self._client.post(
                "/execute",
                json={
                    "idempotency_key": idempotency_key,
                    "action_type": action_type,
                    "session_id": session_id,
                    "policy_verdict_id": policy_verdict_id,
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "payload": payload,
                },
                headers=inject_trace_context(),
            )
            resp.raise_for_status()
            data = resp.json()
            return outcomes.executed(data["action_type"], data["reference"], replay=data.get("replay", False))
        except httpx.HTTPError as exc:
            reason = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                with suppress(Exception):
                    reason = exc.response.json().get("detail", reason)
            logger.error("execution failed for %s: %s", action_type, reason)
            return outcomes.failed(
                reason,
                message="This service is currently unavailable, please try again later. Apologize briefly and offer to escalate.",
            )

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_execution_client() -> ExecutionClient:
    """Return a cached ExecutionClient bound to the configured execution-service URL."""
    return ExecutionClient(get_settings().execution_service_url)
