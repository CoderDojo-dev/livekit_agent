"""ticketing-glpi MCP server (streamable HTTP): full GLPI ticket lifecycle.

Run: python -m ticketing_glpi.server  (serves streamable HTTP at http://HOST:PORT/mcp)

Exposes create / status / update / resolve / close / delete / lookup as MCP tools, plus a plain
HTTP GET /health so platform liveness probes (scripts/health_check.py, Docker/K8s) get a 200
instead of the 404 that /mcp-only servers return.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from ticketing_glpi.tools.glpi_ticket_ops import (
    close_ticket,
    create_ticket,
    delete_ticket,
    get_ticket_status,
    lookup_tickets,
    resolve_ticket,
    update_ticket,
)

mcp = FastMCP(
    "ticketing-glpi",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8202")),
)

for _tool in (create_ticket, get_ticket_status, update_ticket, resolve_ticket,
              close_ticket, delete_ticket, lookup_tickets):
    mcp.tool()(_tool)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Liveness probe. Reports the active GLPI connector mode without touching the network."""
    mode = "live" if os.getenv("CONNECTOR_MODE", "mock").lower() == "live" else "mock"
    return JSONResponse({"status": "ok", "service": "ticketing-glpi", "connector_mode": mode})


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
