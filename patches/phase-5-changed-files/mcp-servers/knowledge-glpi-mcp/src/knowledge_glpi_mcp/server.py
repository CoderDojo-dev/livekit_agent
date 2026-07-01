"""Internal MCP server (streamable HTTP) exposing low-risk, reusable read tools (ADR section 5.4).

Phase 5 exposes knowledge_search only. GLPI ticket tools are registered here in Phase 9.
Run: python -m knowledge_glpi_mcp.server  (serves streamable HTTP at http://HOST:PORT/mcp)
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from knowledge_glpi_mcp.tools.knowledge_search import knowledge_search

mcp = FastMCP(
    "knowledge-glpi",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8201")),
)

# Register the tool (decorator applied programmatically keeps one-file-per-tool, section 11).
mcp.tool()(knowledge_search)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()