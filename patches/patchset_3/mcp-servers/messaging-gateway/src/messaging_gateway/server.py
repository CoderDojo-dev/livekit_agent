"""messaging-gateway MCP server (streamable HTTP). Run: python -m messaging_gateway.server (/mcp)."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from messaging_gateway.tools.messaging_ops import send_sms, send_whatsapp

mcp = FastMCP(
    "messaging-gateway",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8203")),
)

for _tool in (send_sms, send_whatsapp):
    mcp.tool()(_tool)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()