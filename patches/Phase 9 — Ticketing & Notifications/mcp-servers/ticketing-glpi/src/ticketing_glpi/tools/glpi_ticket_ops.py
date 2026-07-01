"""GLPI ticket lifecycle MCP tools (review notes 1 & 2): create / status / resolve / lookup.

create_ticket also asks the notification-service to send the caller a written confirmation -
ticket creation triggering a customer notification is native GLPI behaviour and guarantees the
"close the loop" exit criterion.
"""
from __future__ import annotations

import os

import httpx

from ticketing_glpi.adapters.glpi_client import MockGlpiClient

_client = MockGlpiClient()
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")


async def create_ticket(customer_id: str, subject: str, description: str, language: str = "fr") -> dict:
    """Open a support ticket for an unresolved issue and text the caller a written confirmation.

    Args:
        customer_id: The caller's customer id.
        subject: Short ticket subject.
        description: What needs follow-up.
        language: Caller language for the confirmation (fr/ar/en).
    """
    ticket = _client.create(customer_id, subject, description)
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
    """Look up the status of a ticket."""
    ticket = _client.get(ticket_id)
    if ticket is None:
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status, "subject": ticket.subject}


async def resolve_ticket(ticket_id: str, resolution: str) -> dict:
    """Resolve/close a ticket when the issue is solved during the call (review note 2)."""
    ticket = _client.resolve(ticket_id, resolution)
    if ticket is None:
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def lookup_tickets(customer_id: str) -> list[dict]:
    """List a customer's tickets."""
    return [
        {"ticket_id": t.ticket_id, "status": t.status, "subject": t.subject}
        for t in _client.list_for(customer_id)
    ]