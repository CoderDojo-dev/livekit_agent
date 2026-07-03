"""knowledge_search MCP tool (read-only; every persona may call it).

Proxies to the knowledge-service /search. Returns passages each carrying a 'source' so the
agent can cite it.
"""

import os

import httpx

KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8102")


async def knowledge_search(query: str, top_k: int = 4) -> list[dict]:
    """Search the telecom knowledge base for offers, procedures and FAQs.

    Args:
        query: An English search query describing what the caller needs.
        top_k: Maximum number of passages to return.

    Returns:
        A list of passages, each with 'text', 'source', and 'score'. Cite the 'source'.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{KNOWLEDGE_SERVICE_URL}/search",
            json={"query": query, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json().get("passages", [])