"""ticketing-glpi MCP server (streamable HTTP): GLPI ticket lifecycle (review note 1).

Run: python -m ticketing_glpi.server  (serves streamable HTTP at http://HOST:PORT/mcp)
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ticketing_glpi.tools.glpi_ticket_ops import (
    create_ticket,
    get_ticket_status,
    lookup_tickets,
    resolve_ticket,
)

mcp = FastMCP(
    "ticketing-glpi",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8202")),
)

for _tool in (create_ticket, get_ticket_status, resolve_ticket, lookup_tickets):
    mcp.tool()(_tool)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()