"""knowledge_search MCP tool (read-only; every persona may call it).

Proxies to the knowledge-service /search. Returns passages each carrying a 'source' so the
agent can cite it.

A knowledge-base problem must never take the caller's line down. Since RAG phase 4 the service
answers 503 rather than silently serving term-overlap results, and `raise_for_status()` would
turn that into an exception inside the tool call: the LLM emits a tool call, the tool raises,
and the agent produces no speech - the caller hears silence and hangs up. An empty result is
strictly better: the agent says it does not have that information and the conversation
continues. The failure is loud in the logs, not on the call.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8102")

_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
# A voice caller is waiting: a slow answer is a failed answer. Retrieval is ~50ms warm, so this
# is an outage guard, not a working budget.
_TIMEOUT_S = float(os.getenv("KNOWLEDGE_SEARCH_TIMEOUT_S", "5.0"))


def _internal_headers() -> dict:
    return {"X-API-Key": _INTERNAL_API_KEY} if _INTERNAL_API_KEY else {}


async def knowledge_search(query: str, top_k: int = 4) -> list[dict]:
    """Search the telecom knowledge base for offers, procedures and FAQs.

    Args:
        query: An English search query describing what the caller needs.
        top_k: Maximum number of passages to return.

    Returns:
        A list of passages, each with 'text', 'source', and 'score'. Cite the 'source'.
        An empty list means the knowledge base has nothing relevant - say so rather than
        guessing an answer.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                f"{KNOWLEDGE_SERVICE_URL}/search",
                json={"query": query, "top_k": top_k},
                headers=_internal_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("passages", [])
    except httpx.HTTPStatusError as exc:
        # 503 = index unusable (empty collection, embedder down). Nothing to cite; do not freeze.
        logger.error(
            "knowledge_search: %s returned %s: %s",
            KNOWLEDGE_SERVICE_URL, exc.response.status_code, exc.response.text[:200],
        )
        return []
    except httpx.HTTPError as exc:  # timeout, DNS, connection refused
        logger.error("knowledge_search: %s unreachable: %s", KNOWLEDGE_SERVICE_URL, exc)
        return []
