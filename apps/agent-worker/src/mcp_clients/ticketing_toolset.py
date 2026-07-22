"""[VERIFY] Scoped MCPToolset over the ticketing-glpi MCP server (ADR section 5.4; review note 1).

Same confirmed pattern as the knowledge toolset. Ticketing is its own MCP server, separate from
knowledge. Per-agent scoping: only personas that open/resolve tickets include this toolset.
"""
from __future__ import annotations

from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client  # type: ignore[attr-defined]

from livekit.agents import mcp

_DEFAULT_TOOLS = ("create_ticket", "get_ticket_status", "resolve_ticket", "lookup_tickets")


def build_ticketing_toolset(allowed_tools: Iterable[str] = _DEFAULT_TOOLS):
    """Return an MCPToolset exposing only ``allowed_tools`` from the ticketing MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().ticketing_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="ticketing-glpi", mcp_server=server)
