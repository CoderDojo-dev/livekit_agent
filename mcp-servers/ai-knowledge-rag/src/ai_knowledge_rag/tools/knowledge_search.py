"""knowledge_search MCP tool (read-only; every persona may call it).

Proxies to the knowledge-service /search and returns a structured status.

Version 2 (patch v77): the return contract changes from ``list[dict]`` to ``dict``.
The old signature returned ``[]`` when nothing was relevant, and FastMCP's
``_convert_to_content`` chains an empty list into *zero content blocks*; livekit-agents
1.6.5's ``_default_tool_result_resolver`` then raises
``ToolError("Tool '...' completed without producing a result.")`` when
``len(ctx.result.content) == 0`` (LiveKit only reads ``result.content``, ignoring
``structuredContent``). The tool now returns a status-carrying dict:

- ``{"status": "ok", "passages": [...]}`` — relevant passages found.
- ``{"status": "no_match", "passages": [], "detail": ...}`` — nothing relevant
  (replaces the old empty list; the agent can say so instead of guessing).
- ``{"status": "unavailable", "passages": [], "detail": ...}`` — the knowledge
  service could not answer (503, timeout, network); never silently empty.

A knowledge-base problem must never take the caller's line down: an empty list used to
fail the whole tool call; a status dict always produces speakable content, and failures
stay loud in the logs, not on the call.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8102")

_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
# A voice caller is waiting: a slow answer is a failed answer. Retrieval is ~50ms warm,
# so this is an outage guard, not a working budget.
_TIMEOUT_S = float(os.getenv("KNOWLEDGE_SEARCH_TIMEOUT_S", "5.0"))


def _internal_headers() -> dict:
    return {"X-API-Key": _INTERNAL_API_KEY} if _INTERNAL_API_KEY else {}


def _ok(passages: list) -> dict:
    """Passages found; the LLM can cite their sources."""
    return {"status": "ok", "passages": passages}


def _no_match() -> dict:
    """Nothing relevant; the LLM must say it does not know."""
    return {
        "status": "no_match",
        "passages": [],
        "detail": "The knowledge base contains nothing relevant for this query.",
    }


def _unavailable(detail: str) -> dict:
    """Knowledge service could not answer; the LLM must not guess."""
    return {"status": "unavailable", "passages": [], "detail": detail}


async def knowledge_search(query: str, top_k: int = 4) -> dict:
    """Search the telecom knowledge base for offers, procedures and FAQs.

    Args:
        query: An English search query describing what the caller needs.
        top_k: Maximum number of passages to return.

    Returns:
        A dict with a ``status`` key:
          - "ok": ``passages`` holds the ranked passages; cite their ``source``.
          - "no_match": nothing relevant; tell the caller you do not have that
            information, rather than guessing.
          - "unavailable": the knowledge service could not answer (503, timeout,
            network); say you cannot look it up right now and continue.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                f"{KNOWLEDGE_SERVICE_URL}/search",
                json={"query": query, "top_k": top_k},
                headers=_internal_headers(),
            )
            resp.raise_for_status()
            passages = resp.json().get("passages", [])
    except httpx.HTTPStatusError as exc:
        # 503 = index unusable (empty collection, embedder down). Nothing to cite.
        logger.error(
            "knowledge_search: %s returned %s: %s",
            KNOWLEDGE_SERVICE_URL, exc.response.status_code, exc.response.text[:200],
        )
        return _unavailable(f"knowledge-service returned {exc.response.status_code}")
    except httpx.HTTPError as exc:  # timeout, DNS, connection refused
        logger.error("knowledge_search: %s unreachable: %s", KNOWLEDGE_SERVICE_URL, exc)
        return _unavailable("knowledge-service unreachable")

    if not passages:
        logger.info("knowledge_search: no passage cleared the relevance gates for %r", query)
        return _no_match()

    return _ok(passages)
