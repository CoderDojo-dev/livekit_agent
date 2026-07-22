"""Postgres mirror of GLPI tickets (spec section 10): the durable, queryable local projection.

GLPI stays the source of truth, but the mirror is what makes tickets durable across restarts,
answerable in real time on the voice path, and readable by a future supervisor UI from ONE clean
table (ticketing.tickets). Every function is best-effort and gated on DATABASE_URL, so the MCP
server still runs mock-only when no database is configured.

The mirror stores the full row - customer_id, subscription_id, category, priority, status - so a
caller's ticket history can be answered locally without a GLPI round trip, and status changes an
admin makes in GLPI are reflected back by upsert_from_glpi() during lookups.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = {"network_complaint", "formal_complaint", "technical", "billing", "other"}
_ALLOWED_STATUS = {"open", "in_progress", "pending", "resolved", "closed"}
_ALLOWED_PRIORITY = {"low", "medium", "high", "urgent"}


def normalize_category(category: str | None) -> str:
    """Coerce a free category to the ticketing.tickets vocabulary (default 'other')."""
    return category if category in _ALLOWED_CATEGORIES else "other"


def _normalize_status(status: str | None) -> str:
    return status if status in _ALLOWED_STATUS else "open"


def _normalize_priority(priority: str | None) -> str | None:
    return priority if priority in _ALLOWED_PRIORITY else None


def _enabled() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def _row_to_dict(row) -> dict:
    """Shape a Ticket row for tool responses (the shape the agent and a future UI consume)."""
    return {
        "ticket_id": row.glpi_ticket_id,
        "status": row.status,
        "subject": row.subject,
        "category": row.category,
        "priority": row.priority,
        "customer_id": str(row.customer_id) if row.customer_id else None,
        "subscription_id": str(row.subscription_id) if row.subscription_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
    }


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
                priority=_normalize_priority(priority),
            ))
    except Exception as exc:
        logger.warning("ticket mirror create failed (%s): %s", glpi_ticket_id, exc)


def mirror_update(glpi_ticket_id: str, subject: str | None = None,
                  category: str | None = None, priority: str | None = None,
                  status: str | None = None) -> None:
    """Patch a mirror row (only the provided fields) and bump last_synced_at."""
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is None:
                return
            if subject is not None:
                row.subject = subject[:255] or None
            if category is not None:
                row.category = normalize_category(category)
            if priority is not None:
                row.priority = _normalize_priority(priority)
            if status is not None:
                row.status = _normalize_status(status)
            row.last_synced_at = datetime.now(UTC)
    except Exception as exc:
        logger.warning("ticket mirror update failed (%s): %s", glpi_ticket_id, exc)


def mirror_set_status(glpi_ticket_id: str, status: str) -> None:
    """Set a mirror row's status (used by resolve/close) and bump last_synced_at."""
    mirror_update(glpi_ticket_id, status=status)


def mirror_resolve(glpi_ticket_id: str) -> None:
    """Mark the mirror row resolved (kept for backward compatibility)."""
    mirror_update(glpi_ticket_id, status="resolved")


def mirror_delete(glpi_ticket_id: str) -> bool:
    """Delete a mirror row. Returns True when a row was removed."""
    if not _enabled():
        return False
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is None:
                return False
            session.delete(row)
            return True
    except Exception as exc:
        logger.warning("ticket mirror delete failed (%s): %s", glpi_ticket_id, exc)
        return False


def upsert_from_glpi(glpi_ticket_id: str, customer_id: str | None, subject: str | None,
                     status: str, category: str = "other",
                     subscription_id: str | None = None) -> None:
    """Reconcile a ticket seen in GLPI into the mirror (insert or refresh status/subject).

    This is what reflects an admin's GLPI-side change back into the local view: when a lookup
    reads GLPI directly, the fresh status is written through so the next local read is current.
    """
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket
    from persistence.util import to_uuid

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is None:
                session.add(Ticket(
                    glpi_ticket_id=glpi_ticket_id,
                    customer_id=to_uuid(customer_id),
                    subscription_id=to_uuid(subscription_id),
                    subject=(subject or "")[:255] or None,
                    category=normalize_category(category),
                    status=_normalize_status(status),
                ))
            else:
                row.status = _normalize_status(status)
                if subject:
                    row.subject = subject[:255]
                row.last_synced_at = datetime.now(UTC)
    except Exception as exc:
        logger.warning("ticket mirror upsert failed (%s): %s", glpi_ticket_id, exc)


def read_status(glpi_ticket_id: str) -> dict | None:
    """Return the mirror view of a ticket, or None if absent / mirror disabled."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            return _row_to_dict(row) if row is not None else None
    except Exception as exc:
        logger.warning("ticket mirror read failed (%s): %s", glpi_ticket_id, exc)
        return None


def read_for_customer(customer_id: str) -> list[dict] | None:
    """Return a customer's mirrored tickets (newest first), or None when disabled/unavailable."""
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
            rows = session.scalars(
                select(Ticket).where(Ticket.customer_id == cid)
                .order_by(Ticket.created_at.desc())
            )
            return [_row_to_dict(row) for row in rows]
    except Exception as exc:
        logger.warning("ticket mirror list failed (%s): %s", customer_id, exc)
        return None


def read_glpi_user_id(customer_id: str) -> int | None:
    """Return a customer's stored GLPI user id, or None (mirror disabled / no customer / unset)."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.crm import Customer
    from persistence.util import to_uuid

    cid = to_uuid(customer_id)
    if cid is None:
        return None
    try:
        with session_scope() as session:
            customer = session.get(Customer, cid)
            return customer.glpi_user_id if customer is not None else None
    except Exception as exc:
        logger.warning("read glpi_user_id failed (%s): %s", customer_id, exc)
        return None


def write_glpi_user_id(customer_id: str, glpi_user_id: int) -> bool:
    """Persist a customer's GLPI user id (the permanent customer<->requester mapping)."""
    if not _enabled():
        return False
    from persistence.engine import session_scope
    from persistence.models.crm import Customer
    from persistence.util import to_uuid

    cid = to_uuid(customer_id)
    if cid is None:
        return False
    try:
        with session_scope() as session:
            customer = session.get(Customer, cid)
            if customer is None:
                return False
            customer.glpi_user_id = glpi_user_id
            return True
    except Exception as exc:
        logger.warning("write glpi_user_id failed (%s): %s", customer_id, exc)
        return False


def customers_without_glpi_user() -> list[dict]:
    """Return active customers that have no glpi_user_id yet (for backfill). [] when disabled."""
    if not _enabled():
        return []
    from sqlalchemy import select

    from persistence.engine import session_scope
    from persistence.models.crm import Customer

    try:
        with session_scope() as session:
            rows = session.scalars(
                select(Customer).where(Customer.glpi_user_id.is_(None),
                                       Customer.status == "active")
            )
            return [
                {
                    "customer_id": str(c.id),
                    "login": c.national_id or str(c.id),
                    "first_name": c.first_name or "",
                    "last_name": c.last_name or "",
                    "email": c.email or "",
                }
                for c in rows
            ]
    except Exception as exc:
        logger.warning("customers_without_glpi_user failed: %s", exc)
        return []
