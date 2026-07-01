"""Postgres mirror of GLPI tickets (spec section 10): a thin durable cache pointing at the GLPI id.

GLPI remains the source of truth; this mirror makes the local view durable across restarts and
queryable by the platform. Every function is best-effort and gated on DATABASE_URL, so the MCP
server still runs (mock-only) when no database is configured.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = {"network_complaint", "formal_complaint", "technical", "billing", "other"}


def normalize_category(category: str | None) -> str:
    """Coerce a free category to the spec's ticketing.tickets vocabulary (default 'other')."""
    return category if category in _ALLOWED_CATEGORIES else "other"


def _enabled() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def mirror_create(glpi_ticket_id: str, customer_id: str | None, subject: str | None,
                  category: str = "other", subscription_id: str | None = None,
                  priority: str | None = None) -> None:
    """Insert a mirror row for a freshly created GLPI ticket (idempotent on glpi_ticket_id)."""
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket
    from persistence.util import to_uuid

    try:
        with session_scope() as session:
            if session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id)):
                return
            session.add(Ticket(
                glpi_ticket_id=glpi_ticket_id,
                customer_id=to_uuid(customer_id),
                subscription_id=to_uuid(subscription_id),
                subject=(subject or "")[:255] or None,
                category=normalize_category(category),
                status="open",
                priority=priority,
            ))
    except Exception as exc:  # noqa: BLE001 - mirror must never break ticket creation
        logger.warning("ticket mirror create failed (%s): %s", glpi_ticket_id, exc)


def mirror_resolve(glpi_ticket_id: str) -> None:
    """Mark the mirror row resolved + bump last_synced_at."""
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is not None:
                row.status = "resolved"
                row.last_synced_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ticket mirror resolve failed (%s): %s", glpi_ticket_id, exc)


def read_status(glpi_ticket_id: str) -> dict | None:
    """Return the mirror view of a ticket, or None if absent / mirror disabled."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is None:
                return None
            return {"ticket_id": row.glpi_ticket_id, "status": row.status, "subject": row.subject}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ticket mirror read failed (%s): %s", glpi_ticket_id, exc)
        return None


def read_for_customer(customer_id: str) -> list[dict] | None:
    """Return a customer's mirrored tickets, or None when the mirror is disabled/unavailable."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket
    from persistence.util import to_uuid

    cid = to_uuid(customer_id)
    if cid is None:
        return None
    try:
        with session_scope() as session:
            rows = session.scalars(select(Ticket).where(Ticket.customer_id == cid))
            return [{"ticket_id": r.glpi_ticket_id, "status": r.status, "subject": r.subject} for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("ticket mirror list failed (%s): %s", customer_id, exc)
        return None