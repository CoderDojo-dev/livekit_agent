"""Agent-side ticketing facades (identity-injecting wrappers over the ticketing-glpi MCP tools).

Why these exist instead of exposing the raw MCP tools to the model: the caller's identity
(customer_id, subscription_id) lives in the session's CustomerContext, resolved from the MSISDN
at call start. The MCP server runs in a separate process and cannot see it, so if the model were
asked to pass customer_id it would guess or omit it - which is exactly why every mirrored ticket
had a NULL customer_id. These wrappers inject the VERIFIED ids from session context, so the model
only supplies the human content (subject, description) and the platform supplies identity.

They also give the agent the proactive behaviour the product needs: check_customer_tickets lets
a persona see a caller's open tickets and tell them where their problem stands, in French.
"""
from __future__ import annotations

import json
import logging
import os

from livekit.agents import RunContext, function_tool

_TICKETING_HTTP_URL = os.getenv(
    "TICKETING_HTTP_URL",
    os.getenv("TICKETING_MCP_URL", "http://localhost:8202/mcp").replace("/mcp", ""),
)
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
logger = logging.getLogger(__name__)


def _customer(context: RunContext):
    """The caller's verified context snapshot, or None when the line is unresolved."""
    user_data = getattr(context.session, "userdata", None)
    return getattr(user_data, "customer_context", None) if user_data else None


class TicketingUnavailable(RuntimeError):
    """The ticketing service could not be reached or errored. Surfaced as an honest failure."""


def _extract_result(result: object, tool: str) -> dict | list | None:
    """Pull a tool's return value out of an MCP CallToolResult.

    Prefers ``structuredContent`` (MCP 2025-06+), but falls back to the JSON text carried in
    ``content`` - which is what our FastMCP server actually populates (``structuredContent`` comes
    back ``None``). Reading only ``structuredContent`` was the ticketing bug: every call returned
    ``None`` and the wrappers reported "unavailable" even though GLPI had created the ticket.

    FastMCP wraps list/scalar returns under ``{"result": ...}``; we unwrap that consistently in both
    paths, so a dict return (e.g. ``{"ticket_id": ...}``) passes through untouched while a list
    return (``lookup_tickets``) comes back as a list whether or not it was wrapped.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured

    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            logger.warning("ticketing tool %s returned non-JSON content: %.200s", tool, text)
            return None
        return parsed.get("result", parsed) if isinstance(parsed, dict) else parsed

    return None


async def _mcp_call(tool: str, arguments: dict) -> dict | list | None:
    """Invoke a ticketing-glpi MCP tool over streamable HTTP and return its structured result.

    Raises TicketingUnavailable on any transport/protocol failure so the caller-facing wrappers
    can tell the truth ("I can't reach the ticketing system right now") instead of letting a raw
    exception crash the tool call and leave the agent silent. There is NO fake fallback: a real
    failure is reported as a failure.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = os.getenv("TICKETING_MCP_URL", "http://localhost:8202/mcp")
    headers = {"X-API-Key": _INTERNAL_API_KEY} if _INTERNAL_API_KEY else {}
    try:
        from observability_kit.telemetry import inject_trace_context
        headers = inject_trace_context(headers)
    except Exception:
        pass

    try:
        async with streamablehttp_client(url, headers=headers) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
                if getattr(result, "isError", False):
                    raise TicketingUnavailable(f"ticketing tool {tool!r} returned an error")
                return _extract_result(result, tool)
    except TicketingUnavailable:
        raise
    except Exception as exc:  # connection refused, timeout, protocol error
        logger.error("ticketing MCP call %s failed: %s", tool, exc)
        raise TicketingUnavailable(str(exc)) from exc


# What every wrapper returns when ticketing is unreachable. The message tells the model to be
# honest with the caller and never invent a ticket or a status.
def _unavailable(extra: dict | None = None) -> dict:
    payload = {
        "outcome": "unavailable",
        "message": (
            "The ticketing system is unavailable right now. Tell the caller honestly, in their "
            "language, that you cannot access or record tickets at the moment and will try later. "
            "Do NOT invent a ticket, a reference, or a status."
        ),
    }
    if extra:
        payload.update(extra)
    return payload


@function_tool()
async def create_support_ticket(
    context: RunContext,
    subject: str,
    description: str,
    category: str = "other",
    priority: str = "",
) -> dict:
    """Open a support ticket for an issue that could not be solved on the call.

    Identity (customer + subscription) is taken from the verified session context, not from you.
    You supply only the human content.

    Args:
        subject: Short ticket subject in the caller's language.
        description: What needs follow-up.
        category: network_complaint / formal_complaint / technical / billing / other.
        priority: low / medium / high / urgent (optional; leave empty if unsure).
    """
    customer = _customer(context)
    if customer is None:
        return {"outcome": "unavailable",
                "message": "No active line is resolved for this caller; cannot open a ticket."}

    language = getattr(customer, "preferred_language", "fr") or "fr"
    try:
        result = await _mcp_call("create_ticket", {
            "customer_id": customer.customer_id,
            "subject": subject,
            "description": description,
            "language": language,
            "category": category,
            "subscription_id": customer.subscription_id or "",
            "priority": priority or "",
            "requester_glpi_id": getattr(customer, "glpi_user_id", None),
        })
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def check_customer_tickets(context: RunContext) -> dict:
    """List the caller's existing tickets so you can tell them where their problem stands.

    Use this proactively when a caller mentions a problem: if an open ticket already covers it,
    reassure them it is being handled; if one is resolved, tell them the good news. Identity is
    taken from the verified session context.
    """
    customer = _customer(context)
    if customer is None:
        return {"outcome": "unavailable", "tickets": [],
                "message": "No active line is resolved for this caller."}

    try:
        result = await _mcp_call("lookup_tickets", {
            "customer_id": customer.customer_id,
            "requester_glpi_id": getattr(customer, "glpi_user_id", None),
        })
    except TicketingUnavailable:
        return _unavailable({"tickets": []})
    tickets = result if isinstance(result, list) else []
    open_states = {"open", "in_progress", "pending"}
    open_tickets = [t for t in tickets if t.get("status") in open_states]
    resolved = [t for t in tickets if t.get("status") in {"resolved", "closed"}]
    return {
        "outcome": "listed",
        "total": len(tickets),
        "open_count": len(open_tickets),
        "resolved_count": len(resolved),
        "tickets": tickets,
        "message": (
            "Summarize for the caller in their language: if an open ticket matches their "
            "problem, tell them it is registered and being handled; if a matching ticket is "
            "resolved, tell them the good news. Never invent a ticket that is not in this list."
        ),
    }


@function_tool()
async def get_ticket_state(context: RunContext, ticket_id: str) -> dict:
    """Check the current status of one ticket by its reference (e.g. 'GLPI-42')."""
    try:
        result = await _mcp_call("get_ticket_status", {"ticket_id": ticket_id})
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def mark_ticket_resolved(context: RunContext, ticket_id: str, resolution: str) -> dict:
    """Resolve a ticket when the caller's issue was solved during the call.

    Args:
        ticket_id: The ticket reference (e.g. 'GLPI-42').
        resolution: A short note on how it was solved.
    """
    try:
        result = await _mcp_call("resolve_ticket", {"ticket_id": ticket_id, "resolution": resolution})
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def update_support_ticket(
    context: RunContext,
    ticket_id: str,
    subject: str = "",
    description: str = "",
    priority: str = "",
    category: str = "",
) -> dict:
    """Update an existing ticket's subject, description, priority, or category."""
    try:
        result = await _mcp_call("update_ticket", {
            "ticket_id": ticket_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "category": category,
        })
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]
