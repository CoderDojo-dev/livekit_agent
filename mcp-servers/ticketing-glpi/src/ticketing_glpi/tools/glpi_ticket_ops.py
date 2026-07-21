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

_client = None


def _glpi():
    """Lazily build the live GLPI client on first use.

    Lazy so the module imports even before GLPI env is loaded (the /health route and tests do
    not need a live client); the first ticket operation is what requires - and validates - a
    real GLPI, raising GlpiConfigError if it is not configured.
    """
    global _client
    if _client is None:
        _client = get_glpi_client()
    return _client

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
    # Resolve the caller's GLPI requester id from the stored mapping when not supplied, so the
    # ticket is filed under a real GLPI user and becomes searchable by requester.
    if not requester_glpi_id:
        requester_glpi_id = await asyncio.to_thread(mirror.read_glpi_user_id, customer_id)
    ticket = await asyncio.to_thread(
        _glpi().create, customer_id, subject, description,
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
                    # Centralized resolution: the notification-service maps customer_id -> the
                    # customer's WhatsApp/phone/email itself. We never pass a contact handle.
                    "customer_id": customer_id,
                    "channel": "whatsapp",
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
    live = await asyncio.to_thread(_glpi().get, ticket_id)
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
        _glpi().update, ticket_id, subject or None, description or None,
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
    ticket = await asyncio.to_thread(_glpi().resolve, ticket_id, resolution)
    await asyncio.to_thread(mirror.mirror_set_status, ticket_id, "resolved")
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "resolved"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def close_ticket(ticket_id: str) -> dict:
    """Close a ticket (GLPI status=6 + mirror)."""
    ticket = await asyncio.to_thread(_glpi().close, ticket_id)
    await asyncio.to_thread(mirror.mirror_set_status, ticket_id, "closed")
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "closed"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def delete_ticket(ticket_id: str) -> dict:
    """Delete a ticket from GLPI and the mirror (used to withdraw a mistaken ticket)."""
    deleted = await asyncio.to_thread(_glpi().delete, ticket_id)
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

    if not requester_glpi_id:
        requester_glpi_id = await asyncio.to_thread(mirror.read_glpi_user_id, customer_id)
    live = await asyncio.to_thread(_glpi().list_for, requester_glpi_id or customer_id)
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


async def ensure_customer_glpi_user(customer_id: str, login: str, first_name: str = "",
                                    last_name: str = "", email: str = "") -> dict:
    """Ensure the customer has a GLPI user and persist the mapping (customer.glpi_user_id).

    Called when a customer is created (and by the backfill for existing customers). Idempotent:
    if the mapping already exists it is returned unchanged; otherwise the GLPI user is
    found-or-created and the id is written back to crm.customers.
    """
    existing = await asyncio.to_thread(mirror.read_glpi_user_id, customer_id)
    if existing:
        return {"customer_id": customer_id, "glpi_user_id": existing, "created": False}

    glpi_user_id = await asyncio.to_thread(
        _glpi().ensure_user, login or customer_id, first_name, last_name, email,
    )
    if glpi_user_id is None:
        return {"customer_id": customer_id, "glpi_user_id": None, "created": False,
                "error": "GLPI user could not be created"}

    await asyncio.to_thread(mirror.write_glpi_user_id, customer_id, glpi_user_id)
    return {"customer_id": customer_id, "glpi_user_id": glpi_user_id, "created": True}


def backfill_glpi_users() -> dict:
    """Create GLPI users for all active customers missing a mapping. Idempotent; run any time.

    Synchronous entrypoint (console script) so operators can map existing customers in one pass.
    """
    import asyncio as _asyncio

    pending = mirror.customers_without_glpi_user()
    mapped = 0
    for row in pending:
        result = _asyncio.run(ensure_customer_glpi_user(
            row["customer_id"], row["login"], row["first_name"], row["last_name"], row["email"],
        ))
        if result.get("glpi_user_id"):
            mapped += 1
    print(f"GLPI_USER_BACKFILL pending={len(pending)} mapped={mapped}")
    return {"pending": len(pending), "mapped": mapped}
