"""[VERIFY] Scoped MCPToolset over the ai-knowledge-rag MCP server (ADR section 5.4).

Stable pattern (confirmed): MCPToolset(id=..., mcp_server=MCPServerHTTP(url=.../mcp,
allowed_tools=[...])). URLs ending '/mcp' use streamable HTTP. The deprecated mcp_servers=[...]
param is NOT used. Knowledge is now its own MCP server (review note 1), separate from GLPI
ticketing (ticketing-glpi, Phase 9). Per-agent scoping: each persona builds its own toolset.
"""
from __future__ import annotations

import os
from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client  # type: ignore[attr-defined]

from livekit.agents import mcp

_DEFAULT_MCP_TIMEOUT_S = 9.0


def _mcp_timeout_s() -> float:
    """MCP client timeout; invalid env values fall back to the safe default."""
    try:
        return float(os.environ.get("KNOWLEDGE_MCP_TIMEOUT_S", _DEFAULT_MCP_TIMEOUT_S))
    except ValueError:
        return _DEFAULT_MCP_TIMEOUT_S


def build_knowledge_toolset(allowed_tools: Iterable[str] = ("knowledge_search",)):
    """Return an MCPToolset exposing only ``allowed_tools`` from the knowledge MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().knowledge_mcp_url,
        allowed_tools=list(allowed_tools),
        client_session_timeout_seconds=_mcp_timeout_s(),
    )
    return mcp.MCPToolset(id="ai-knowledge-rag", mcp_server=server)
