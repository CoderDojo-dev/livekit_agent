"""ticketing-glpi MCP server (streamable HTTP): full GLPI ticket lifecycle.

Run: python -m ticketing_glpi.server  (serves streamable HTTP at http://HOST:PORT/mcp)

Exposes create / status / update / resolve / close / delete / lookup as MCP tools, plus a plain
HTTP GET /health so platform liveness probes (scripts/health_check.py, Docker/K8s) get a 200
instead of the 404 that /mcp-only servers return.
"""
from __future__ import annotations

import asyncio
import logging
import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from ticketing_glpi.adapters import mirror
# Reuse the tools module's cached accessor rather than building a second client: it memoises the
# LiveGlpiClient, so the internal route and the MCP tools share one connection-configured client
# and cannot drift apart in credentials or construction.
from ticketing_glpi.tools.glpi_ticket_ops import _glpi
from ticketing_glpi.tools.glpi_ticket_ops import (
    close_ticket,
    create_ticket,
    delete_ticket,
    ensure_customer_glpi_user,
    get_ticket_status,
    lookup_tickets,
    resolve_ticket,
    update_ticket,
)

logger = logging.getLogger(__name__)

# The console may only move a ticket between the states ticketing.tickets already allows. This
# mirrors the table's CheckConstraint exactly, so a value that passes here can never fail the
# mirror write.
_ALLOWED_ADMIN_STATUS = {"open", "in_progress", "pending", "resolved", "closed"}

mcp = FastMCP(
    "ticketing-glpi",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8202")),
)

for _tool in (create_ticket, get_ticket_status, update_ticket, resolve_ticket,
              close_ticket, delete_ticket, lookup_tickets, ensure_customer_glpi_user):
    mcp.tool()(_tool)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Liveness probe. Reports whether GLPI is configured, without touching the network.

    Ticketing is live-only: there is no mock. This reports "configured" when the three GLPI
    settings are present (the client will talk to the real GLPI on first use) and "unconfigured"
    when they are missing (the first ticket operation will raise GlpiConfigError). It does NOT
    call GLPI, so it stays fast and never fails the probe on a transient GLPI outage.
    """
    configured = all(os.getenv(name) for name in
                     ("GLPI_BASE_URL", "GLPI_APP_TOKEN", "GLPI_USER_TOKEN"))
    return JSONResponse({
        "status": "ok",
        "service": "ticketing-glpi",
        "glpi": "configured" if configured else "unconfigured",
        "glpi_base_url": os.getenv("GLPI_BASE_URL", ""),
    })


@mcp.custom_route("/internal/tickets/{ticket_id}/admin-update", methods=["POST"])
async def admin_update(request: Request) -> JSONResponse:
    """Apply an administrator's manual ticket change: GLPI first, then the local mirror.

    WHY THIS LIVES HERE RATHER THAN IN business-api
    The GLPI client and its credentials exist in exactly one place. business-api cannot import
    this package (separate container, separate dependency set) and the MCP tool surface is not
    callable over plain HTTP, so the console reaches GLPI through this narrow internal route
    instead of growing a second GLPI client that could drift from this one.

    ORDER IS THE SAFETY PROPERTY
    GLPI is the source of truth, so it is written FIRST. The mirror is only updated once GLPI has
    accepted the change. If GLPI refuses or is unreachable we return 502 and leave the mirror
    untouched — the console then reports the failure honestly rather than showing a status the
    upstream never took. The opposite order would let the two disagree silently, which is the one
    outcome a mirror must never produce.

    The note is written to the mirror only: GLPI's `solution` field is never read back by
    LiveGlpiClient.get(), so a note stored upstream would be invisible to the agent (see
    migration 0020).
    """
    expected = os.getenv("INTERNAL_API_KEY", "")
    if expected and request.headers.get("X-API-Key") != expected:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    ticket_id = request.path_params["ticket_id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    status = (body.get("status") or "").strip()
    note = body.get("note")
    note_author = (body.get("note_author") or "").strip() or None

    if status and status not in _ALLOWED_ADMIN_STATUS:
        return JSONResponse(
            {"error": f"status must be one of {sorted(_ALLOWED_ADMIN_STATUS)}"}, status_code=400
        )
    if not status and note is None:
        return JSONResponse({"error": "nothing to update"}, status_code=400)

    applied_status: str | None = None
    if status:
        try:
            ticket = await asyncio.to_thread(_glpi().update, ticket_id, None, None, None, status)
        except Exception as exc:  # GLPI unreachable / misconfigured / rejected
            logger.warning("admin ticket update failed upstream (%s): %s", ticket_id, exc)
            return JSONResponse({"error": f"glpi update failed: {exc}"}, status_code=502)
        if ticket is None:
            return JSONResponse({"error": "ticket not found in GLPI"}, status_code=404)
        # Trust GLPI's echo of the status over what we asked for.
        applied_status = ticket.status or status

    await asyncio.to_thread(
        mirror.mirror_update,
        ticket_id,
        None,
        None,
        None,
        applied_status,
        note,
        note_author,
    )

    fresh = await asyncio.to_thread(mirror.read_status, ticket_id)
    return JSONResponse({"ok": True, "ticket": fresh or {"ticket_id": ticket_id}})


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
