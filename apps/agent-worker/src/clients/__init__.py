"""Typed clients to domain services (one per service). Each carries its own timeout/retry."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def aclose_all_clients() -> None:
    """Close every typed HTTP client that was actually created during this job.

    The clients are process-global ``functools.lru_cache`` singletons that open a
    persistent ``httpx.AsyncClient`` pool on first use. LiveKit runs each job in its
    own process, so closing them in a per-job shutdown callback releases the pools
    cleanly at end of call. Only getters whose cache is populated are touched, so we
    never open a pool just to close it. Never raises into shutdown.

    NOTE: MCP toolsets (mcp_clients/*) are intentionally NOT closed here — their
    MCPServerHTTP lifecycle is owned by the LiveKit framework and closed with the
    session. Closing them here would double-close.
    """
    # Imported lazily to keep this package import light and avoid import cycles.
    from clients.context_client import get_context_client
    from clients.decision_client import get_decision_client
    from clients.execution_client import get_execution_client
    from clients.nms_client import get_nms_client
    from clients.notification_client import get_notification_client
    from clients.policy_client import get_policy_client

    getters = (
        get_context_client,
        get_decision_client,
        get_execution_client,
        get_nms_client,
        get_notification_client,
        get_policy_client,
    )

    async def _close(getter: Any) -> None:
        # Only close clients that were actually instantiated this job.
        if getter.cache_info().currsize == 0:
            return
        client = getter()
        aclose = getattr(client, "aclose", None)
        if aclose is None:
            return
        try:
            await aclose()
        except Exception as exc:  # cleanup must never break shutdown
            logger.warning("http client cleanup failed for %s: %s", getter.__name__, exc)

    await asyncio.gather(*(_close(getter) for getter in getters))