"""GLPI ticket lifecycle MCP tools: create / status / resolve / close / update / delete / lookup.

GLPI is the source of truth; the Postgres mirror (adapters/mirror.py) is the durable local
projection the agent reads on the voice path and a future UI reads for CRUD. Every write goes to
GLPI first, then the mirror, so the two stay consistent; every read prefers the mirror and
reconciles from GLPI when the mirror is cold, so an admin's GLPI-side status change is reflected
back to the caller on a later turn.

Identity (customer_id / subscription_id) is NOT invented by the model: the agent-side tool
wrappers inject the caller's verified ids from session context before these tools run, which is
why the mirror rows carry a real customer_id instead of NULL.
"""
import asyncio
import os

import httpx

from ticketing_glpi.adapters import mirror
from ticketing_glpi.adapters.glpi_client import get_glpi_client

_client = get_glpi_client()
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _internal_headers() -> dict:
    headers = {"X-API-Key": _INTERNAL_API_KEY} if _INTERNAL_API_KEY else {}
    try:
        from observability_kit.telemetry import inject_trace_context
        return inject_trace_context(headers)
    except Exception:
        return headers


async def create_ticket(customer_id: str, subject: str, description: str,
                        language: str = "fr", category: str = "other",
                        subscription_id: str = "", priority: str = "",
                        requester_glpi_id: int | None = None) -> dict:
    """Open a support ticket for an unresolved issue and text the caller a written confirmation.

    Args:
        customer_id: The caller's customer UUID (injected by the agent from session context).
        subject: Short ticket subject.
        description: What needs follow-up.
        language: Caller language for the confirmation (fr/ar/en).
        category: network_complaint / formal_complaint / technical / billing / other.
        subscription_id: The caller's subscription UUID, when known.
        priority: low / medium / high / urgent (optional).
        requester_glpi_id: The caller's GLPI user id, when mapped (enables live search).
    """
    ticket = await asyncio.to_thread(
        _client.create, customer_id, subject, description,
        mirror.normalize_category(category), priority or None, requester_glpi_id,
    )
    await asyncio.to_thread(
        mirror.mirror_create, ticket.ticket_id, customer_id, subject,
        category, subscription_id or None, priority or None,
    )

    confirmation_sent = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notify",
                json={
                    "customer_id": customer_id,
                    "to": customer_id,
                    "channel": "sms",
                    "template": "ticket_created",
                    "language": language,
                    "params": {"ticket_id": ticket.ticket_id},
                },
                headers=_internal_headers(),
            )
            confirmation_sent = resp.status_code == 200 and resp.json().get("sent", False)
    except httpx.HTTPError:
        confirmation_sent = False

    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "category": ticket.category,
        "priority": ticket.priority,
        "written_confirmation_sent": confirmation_sent,
    }


async def get_ticket_status(ticket_id: str) -> dict:
    """Look up one ticket's status. Reconciles GLPI -> mirror so admin changes are reflected."""
    live = await asyncio.to_thread(_client.get, ticket_id)
    if live is not None:
        # GLPI answered: write the fresh status through so the local view stays current.
        await asyncio.to_thread(
            mirror.upsert_from_glpi, ticket_id, live.customer_id or None,
            live.subject or None, live.status,
        )
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        return {"found": True, **(mirrored or {
            "ticket_id": live.ticket_id, "status": live.status, "subject": live.subject})}

    mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
    if mirrored is not None:
        return {"found": True, **mirrored}
    return {"found": False}


async def update_ticket(ticket_id: str, subject: str = "", description: str = "",
                        priority: str = "", category: str = "", status: str = "") -> dict:
    """Update a ticket's fields (subject/description/priority/category/status) in GLPI + mirror."""
    ticket = await asyncio.to_thread(
        _client.update, ticket_id, subject or None, description or None,
        priority or None, status or None,
    )
    await asyncio.to_thread(
        mirror.mirror_update, ticket_id, subject or None, category or None,
        priority or None, (ticket.status if ticket else status) or None,
    )
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, **mirrored}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status,
            "priority": ticket.priority}


async def resolve_ticket(ticket_id: str, resolution: str) -> dict:
    """Resolve a ticket when the issue is solved during the call (GLPI status=5 + mirror)."""
    ticket = await asyncio.to_thread(_client.resolve, ticket_id, resolution)
    await asyncio.to_thread(mirror.mirror_set_status, ticket_id, "resolved")
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "resolved"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def close_ticket(ticket_id: str) -> dict:
    """Close a ticket (GLPI status=6 + mirror)."""
    ticket = await asyncio.to_thread(_client.close, ticket_id)
    await asyncio.to_thread(mirror.mirror_set_status, ticket_id, "closed")
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "closed"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def delete_ticket(ticket_id: str) -> dict:
    """Delete a ticket from GLPI and the mirror (used to withdraw a mistaken ticket)."""
    deleted = await asyncio.to_thread(_client.delete, ticket_id)
    mirror_deleted = await asyncio.to_thread(mirror.mirror_delete, ticket_id)
    return {"deleted": bool(deleted or mirror_deleted), "ticket_id": ticket_id}


async def lookup_tickets(customer_id: str, requester_glpi_id: int | None = None) -> list[dict]:
    """List a customer's tickets. Mirror first; if cold and live, search GLPI and reconcile.

    The mirror is the fast per-user source of truth. When it is empty for this caller and a live
    GLPI is configured, the requester's tickets are searched in GLPI and written through, so the
    caller's history survives even for tickets opened outside this platform.
    """
    mirrored = await asyncio.to_thread(mirror.read_for_customer, customer_id)
    if mirrored:
        return mirrored

    live = await asyncio.to_thread(_client.list_for, requester_glpi_id or customer_id)
    for ticket in live:
        await asyncio.to_thread(
            mirror.upsert_from_glpi, ticket.ticket_id, customer_id,
            ticket.subject or None, ticket.status,
        )
    if live:
        reconciled = await asyncio.to_thread(mirror.read_for_customer, customer_id)
        if reconciled:
            return reconciled
    return [
        {"ticket_id": t.ticket_id, "status": t.status, "subject": t.subject}
        for t in live
    ]
