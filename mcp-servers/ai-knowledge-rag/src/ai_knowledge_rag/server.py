"""ai-knowledge-rag MCP server (streamable HTTP) exposing knowledge_search only (review note 1).

Run: python -m ai_knowledge_rag.server  (serves streamable HTTP at http://HOST:PORT/mcp)
GLPI ticketing lives in the separate ticketing-glpi server (Phase 9).
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ai_knowledge_rag.tools.knowledge_search import knowledge_search

mcp = FastMCP(
    "ai-knowledge-rag",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8201")),
)

mcp.tool()(knowledge_search)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()