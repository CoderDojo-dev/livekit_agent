"""Callback queue operations: the lifecycle a scheduled callback needs to be a real promise.

Until now a callback was written with status='pending' and never read again - nobody could say
whether it was ever made. This gives the row a life: it can be listed, claimed by exactly one
advisor, completed with an outcome, retried, or cancelled, and a supervisor can see which ones are
overdue.

The claim uses FOR UPDATE SKIP LOCKED for the same reason the advisor registry does: two advisors
opening the queue at the same moment must not both take the same caller.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models.conversation import CallbackSchedule
from persistence.models.crm import Customer
from persistence.models.routing import Advisor

logger = logging.getLogger(__name__)

OPEN = "pending"
COMPLETED = "completed"
CANCELLED = "cancelled"


def _aware(value: datetime | None) -> datetime | None:
    """Normalize to UTC-aware; some drivers return naive datetimes and comparison would raise."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def to_dict(row: CallbackSchedule, customer: Customer | None = None,
            advisor: Advisor | None = None, now: datetime | None = None) -> dict:
    """Serialize a callback for the API, including whether it is past its due time."""
    now = now or datetime.now(UTC)
    scheduled = _aware(row.scheduled_time)
    return {
        "id": str(row.id),
        "status": row.status,
        "scheduled_time": scheduled.isoformat() if scheduled else None,
        # The caller's own words, kept verbatim: an advisor should see "demain matin", not just a
        # timestamp the system guessed.
        "preferred_window": row.preferred_window,
        "reason": row.reason,
        "priority_level": row.priority_level,
        "attempts": row.attempts,
        "outcome_note": row.outcome_note,
        "completed_at": _aware(row.completed_at).isoformat() if row.completed_at else None,
        "overdue": bool(row.status == OPEN and scheduled and scheduled < now),
        "customer_id": str(row.customer_id) if row.customer_id else None,
        "customer_name": (f"{customer.first_name} {customer.last_name}".strip()
                          if customer else None),
        "customer_phone": customer.contact_number if customer else None,
        "assigned_advisor_id": str(row.assigned_advisor_id) if row.assigned_advisor_id else None,
        "assigned_advisor_name": advisor.full_name if advisor else None,
        "session_id": str(row.session_id) if row.session_id else None,
    }


def _hydrate(session: Session, rows: list[CallbackSchedule]) -> list[dict]:
    """Attach customer and advisor detail so the queue is actionable without extra lookups."""
    now = datetime.now(UTC)
    customer_ids = {r.customer_id for r in rows if r.customer_id}
    advisor_ids = {r.assigned_advisor_id for r in rows if r.assigned_advisor_id}
    customers = {c.id: c for c in session.scalars(
        select(Customer).where(Customer.id.in_(customer_ids)))} if customer_ids else {}
    advisors = {a.id: a for a in session.scalars(
        select(Advisor).where(Advisor.id.in_(advisor_ids)))} if advisor_ids else {}
    return [
        to_dict(r, customers.get(r.customer_id), advisors.get(r.assigned_advisor_id), now)
        for r in rows
    ]


def list_callbacks(session: Session, status: str = OPEN, overdue_only: bool = False,
                   limit: int = 100) -> list[dict]:
    """List callbacks, soonest first. ``overdue_only`` narrows to those past their due time."""
    stmt = select(CallbackSchedule).order_by(
        CallbackSchedule.priority_level.desc(), CallbackSchedule.scheduled_time.asc()
    ).limit(limit)
    if status:
        stmt = stmt.where(CallbackSchedule.status == status)
    if overdue_only:
        stmt = stmt.where(CallbackSchedule.scheduled_time < datetime.now(UTC))
    return _hydrate(session, list(session.scalars(stmt)))


def queue_stats(session: Session) -> dict:
    """Queue health for the supervisor dashboard: how many are waiting, and how many are late."""
    now = datetime.now(UTC)
    pending = session.scalar(
        select(func.count()).select_from(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN)
    ) or 0
    overdue = session.scalar(
        select(func.count()).select_from(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN, CallbackSchedule.scheduled_time < now)
    ) or 0
    completed = session.scalar(
        select(func.count()).select_from(CallbackSchedule)
        .where(CallbackSchedule.status == COMPLETED)
    ) or 0
    return {"pending": int(pending), "overdue": int(overdue), "completed": int(completed)}


def claim_next(session: Session, advisor_id: str | None = None) -> dict | None:
    """Atomically take the next due callback; None when the queue is empty.

    SKIP LOCKED so concurrent advisors get different callers instead of colliding on the first row.
    Assignment is recorded so the queue shows who owns each one.
    """
    from persistence.util import to_uuid

    stmt = (
        select(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN,
               CallbackSchedule.assigned_advisor_id.is_(None))
        .order_by(CallbackSchedule.priority_level.desc(),
                  CallbackSchedule.scheduled_time.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = session.scalar(stmt)
    if row is None:
        return None
    aid = to_uuid(advisor_id) if advisor_id else None
    row.assigned_advisor_id = aid
    row.attempts += 1
    row.updated_at = datetime.now(UTC)
    logger.info("callback %s claimed by advisor %s", row.id, advisor_id)
    return _hydrate(session, [row])[0]


def complete_callback(session: Session, callback_id: str, note: str = "",
                      reached: bool = True) -> dict | None:
    """Close a callback with its outcome.

    ``reached=False`` returns it to the queue (unassigned) rather than closing it, because a
    caller who did not pick up has not been helped - the attempt counter already records the try.
    """
    from persistence.util import to_uuid

    cid = to_uuid(callback_id)
    row = session.get(CallbackSchedule, cid) if cid else None
    if row is None:
        return None
    if reached:
        row.status = COMPLETED
        row.completed_at = datetime.now(UTC)
    else:
        row.assigned_advisor_id = None  # back to the queue for another attempt
    row.outcome_note = (note or "")[:500] or row.outcome_note
    row.updated_at = datetime.now(UTC)
    return _hydrate(session, [row])[0]


def cancel_callback(session: Session, callback_id: str, note: str = "") -> dict | None:
    """Cancel a callback (caller no longer needs it, or it was superseded)."""
    from persistence.util import to_uuid

    cid = to_uuid(callback_id)
    row = session.get(CallbackSchedule, cid) if cid else None
    if row is None:
        return None
    row.status = CANCELLED
    row.outcome_note = (note or "")[:500] or row.outcome_note
    row.updated_at = datetime.now(UTC)
    return _hydrate(session, [row])[0]
