"""GLPI ticket lifecycle MCP tools: create / status / resolve / lookup.

GLPI (mock) remains the source of truth; a durable Postgres mirror (spec section 10) is written
on create/resolve and read on status/lookup, falling back to the in-memory mock when no database
is configured. create_ticket also asks the notification-service to text a written confirmation.
"""
import asyncio
import os

import httpx

from ticketing_glpi.adapters import mirror
from ticketing_glpi.adapters.glpi_client import get_glpi_client

_client = get_glpi_client()
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")


async def create_ticket(customer_id: str, subject: str, description: str,
                        language: str = "fr", category: str = "other") -> dict:
    """Open a support ticket for an unresolved issue and text the caller a written confirmation.

    Args:
        customer_id: The caller's customer id.
        subject: Short ticket subject.
        description: What needs follow-up.
        language: Caller language for the confirmation (fr/ar/en).
        category: Ticket category (network_complaint/formal_complaint/technical/billing/other).
    """
    ticket = _client.create(customer_id, subject, description)
    await asyncio.to_thread(mirror.mirror_create, ticket.ticket_id, customer_id, subject, category)

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
            )
            confirmation_sent = resp.status_code == 200 and resp.json().get("sent", False)
    except httpx.HTTPError:
        confirmation_sent = False
    return {"ticket_id": ticket.ticket_id, "status": ticket.status, "written_confirmation_sent": confirmation_sent}


async def get_ticket_status(ticket_id: str) -> dict:
    """Look up the status of a ticket (durable mirror first, mock fallback)."""
    mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
    if mirrored is not None:
        return {"found": True, **mirrored}
    ticket = _client.get(ticket_id)
    if ticket is None:
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status, "subject": ticket.subject}


async def resolve_ticket(ticket_id: str, resolution: str) -> dict:
    """Resolve/close a ticket when the issue is solved during the call (review note 2)."""
    ticket = _client.resolve(ticket_id, resolution)
    await asyncio.to_thread(mirror.mirror_resolve, ticket_id)
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "resolved"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def lookup_tickets(customer_id: str) -> list[dict]:
    """List a customer's tickets (durable mirror first, mock fallback)."""
    mirrored = await asyncio.to_thread(mirror.read_for_customer, customer_id)
    if mirrored is not None:
        return mirrored
    return [
        {"ticket_id": t.ticket_id, "status": t.status, "subject": t.subject}
        for t in _client.list_for(customer_id)
    ]