"""[VERIFY] Scoped MCPToolset over the internal knowledge+GLPI MCP server (ADR section 5.4).

Stable pattern (confirmed): MCPToolset(id=..., mcp_server=MCPServerHTTP(url=.../mcp,
allowed_tools=[...])). URLs ending '/mcp' use streamable HTTP. The deprecated mcp_servers=[...]
param is NOT used. Per-agent scoping: each persona builds its own toolset with an allow-list.
Confirm at build: docs.livekit.io/agents/logic/tools/mcp/. If an individual server fails to
connect, the SDK logs it and the agent still starts.
"""
from __future__ import annotations

from collections.abc import Iterable

from livekit.agents import mcp

from config import get_settings


def build_knowledge_toolset(allowed_tools: Iterable[str] = ("knowledge_search",)):
    """Return an MCPToolset exposing only ``allowed_tools`` from the internal MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().knowledge_glpi_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="knowledge-glpi", mcp_server=server)