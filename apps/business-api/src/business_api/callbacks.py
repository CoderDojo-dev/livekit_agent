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
import os
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from business_api.availability import BUSINESS_TZ, DAY_END_HOUR, DAY_START_HOUR, ScheduleIndex, load_schedule
from persistence.models.conversation import CallbackSchedule
from persistence.models.crm import Customer
from persistence.models.routing import Advisor

logger = logging.getLogger(__name__)

OPEN = "pending"
COMPLETED = "completed"
CANCELLED = "cancelled"

# Slot geometry. Env-driven so the call centre can change its hours without a deploy.
SLOT_MINUTES = int(os.getenv("CALLBACK_SLOT_MINUTES", "30"))
# Never offer a slot the queue cannot honour: an advisor needs time to pick the case up.
LEAD_MINUTES = int(os.getenv("CALLBACK_LEAD_MINUTES", "30"))


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


def _slot_capacity(session: Session, moment: datetime | None = None,
                   index: ScheduleIndex | None = None) -> int:
    """How many callbacks a given instant can hold: one per advisor actually working then.

    Capacity used to be a constant for the whole week, which is why every slot looked identical
    and the agent could never decline a time. It is now derived from the weekly grid and the dated
    exceptions, so Sunday at 08:00 honestly reports zero.

    ``moment=None`` keeps the old meaning (how many advisors are on call at all) for callers that
    only need a yes/no on whether the queue exists.
    """
    index = index or load_schedule(session)
    if moment is None:
        return len(index.advisors)
    return index.capacity_at(moment)


def _slot_bounds(now: datetime, days: int) -> list[datetime]:
    """Every slot start between now+lead and now+days, inside business hours."""
    step = timedelta(minutes=SLOT_MINUTES)
    first = now + timedelta(minutes=LEAD_MINUTES)
    # Round up to the next slot boundary so offered times are always clean (09:00, 09:30).
    # Ceiling, not "next": an instant already on a boundary must stay where it is, otherwise the
    # soonest slot we can offer drifts by a whole step for no reason.
    minute = -(-first.minute // SLOT_MINUTES) * SLOT_MINUTES
    cursor = first.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)
    end = now + timedelta(days=days)
    slots: list[datetime] = []
    while cursor < end:
        # DAY_START_HOUR / DAY_END_HOUR are business-local hours, and cursor is UTC. Comparing
        # them directly silently dropped the first local working hour and let a late UTC hour
        # through. capacity_at() already reasons in local time; this must match it.
        local_hour = cursor.astimezone(BUSINESS_TZ).hour
        if DAY_START_HOUR <= local_hour < DAY_END_HOUR:
            slots.append(cursor)
        cursor = cursor + step
    return slots


def free_slots(session: Session, days: int = 2, limit: int = 6,
               day: str | None = None, skill_tag: str | None = None,
               language: str | None = None) -> list[dict]:
    """Bookable slots, soonest first. Empty list when nobody works in the window asked about.

    ``day`` (YYYY-MM-DD, business timezone) answers "what have you got on Thursday?" without
    scanning the whole horizon - the question a caller actually asks. An empty list stays a
    legitimate answer and MUST be spoken as such: it is the difference between a promise and a lie.
    """
    index = load_schedule(session, skill_tag=skill_tag, language=language)
    if not index.advisors:
        return []

    now = datetime.now(UTC)
    if day:
        try:
            wanted = date.fromisoformat(day)
        except ValueError:
            return []
        horizon_days = max(1, (wanted - now.astimezone(BUSINESS_TZ).date()).days + 1)
        candidates = [
            slot for slot in _slot_bounds(now, horizon_days)
            if slot.astimezone(BUSINESS_TZ).date() == wanted
        ]
    else:
        candidates = _slot_bounds(now, days)
    if not candidates:
        return []

    horizon_end = candidates[-1] + timedelta(minutes=SLOT_MINUTES)
    taken: dict[datetime, int] = {}
    rows = session.scalars(
        select(CallbackSchedule).where(
            CallbackSchedule.status == OPEN,
            CallbackSchedule.scheduled_time >= candidates[0] - timedelta(minutes=SLOT_MINUTES),
            CallbackSchedule.scheduled_time < horizon_end,
        )
    )
    for row in rows:
        booked = _aware(row.scheduled_time)
        if booked is not None:
            taken[booked] = taken.get(booked, 0) + 1

    free: list[dict] = []
    for slot in candidates:
        capacity = index.capacity_at(slot)
        if capacity <= 0:
            continue
        remaining = capacity - taken.get(slot, 0)
        if remaining <= 0:
            continue
        local = slot.astimezone(BUSINESS_TZ)
        free.append({
            "slot_start": slot.isoformat(),
            "slot_minutes": SLOT_MINUTES,
            "remaining": remaining,
            "local_day": local.strftime("%Y-%m-%d"),
            "local_time": local.strftime("%H:%M"),
        })
        if len(free) >= limit:
            break
    return free


def check_slot(session: Session, requested: str, alternatives: int = 3,
               skill_tag: str | None = None, language: str | None = None) -> dict:
    """Answer "can you call me Thursday at 14:00?" with a reason and a way forward.

    A bare False would leave the agent guessing what to say next, and guessing is exactly how it
    starts inventing times. Every refusal therefore carries a machine-readable ``reason`` and the
    nearest real alternatives, so the reply is generated from facts and never from imagination.
    """
    try:
        when = datetime.fromisoformat(requested)
    except ValueError:
        return {"available": False, "reason": "unparsable", "requested": requested,
                "alternatives": []}
    when = when if when.tzinfo is not None else when.replace(tzinfo=BUSINESS_TZ)
    when = when.astimezone(UTC)

    now = datetime.now(UTC)
    index = load_schedule(session, skill_tag=skill_tag, language=language)

    # Snap to the slot grid: a caller says "around two", the queue works in half hours.
    minute = (when.minute // SLOT_MINUTES) * SLOT_MINUTES
    slot = when.replace(minute=minute, second=0, microsecond=0)

    def _nearby() -> list[dict]:
        local_day = slot.astimezone(BUSINESS_TZ).strftime("%Y-%m-%d")
        same_day = free_slots(session, days=7, limit=alternatives, day=local_day,
                              skill_tag=skill_tag, language=language)
        if same_day:
            return same_day
        # Nothing that day: widen rather than dead-end, so the caller always has something to say
        # yes to.
        return free_slots(session, days=7, limit=alternatives,
                          skill_tag=skill_tag, language=language)

    if slot < now + timedelta(minutes=LEAD_MINUTES):
        return {"available": False, "reason": "too_soon", "requested": slot.isoformat(),
                "alternatives": _nearby()}

    capacity = index.capacity_at(slot)
    if capacity <= 0:
        return {"available": False, "reason": "closed", "requested": slot.isoformat(),
                "alternatives": _nearby()}

    used = session.scalar(
        select(func.count()).select_from(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN, CallbackSchedule.scheduled_time == slot)
    ) or 0
    if int(used) >= capacity:
        return {"available": False, "reason": "full", "requested": slot.isoformat(),
                "alternatives": _nearby()}

    local = slot.astimezone(BUSINESS_TZ)
    return {
        "available": True,
        "reason": "ok",
        "slot_start": slot.isoformat(),
        "slot_minutes": SLOT_MINUTES,
        "remaining": capacity - int(used),
        "local_day": local.strftime("%Y-%m-%d"),
        "local_time": local.strftime("%H:%M"),
        "alternatives": [],
    }


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
    Assignment is recorded so the queue shows who owns each one. An advisor resumes the callbacks
    already assigned to them first, then takes unassigned ones - a caller promised "advisor X will
    call you" must not be picked up by someone else while X is busy.
    """
    from persistence.util import to_uuid as _to_uuid

    wanted = _to_uuid(advisor_id) if advisor_id else None
    stmt = (
        select(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN)
    )
    if wanted is not None:
        # An advisor asking for work gets their own callbacks first, then anything unassigned.
        # Without this filter, naming the advisor at booking time would be undone at claim time.
        stmt = stmt.where(
            (CallbackSchedule.assigned_advisor_id == wanted)
            | CallbackSchedule.assigned_advisor_id.is_(None)
        )
    stmt = (
        stmt
        .order_by(CallbackSchedule.priority_level.desc(),
                  CallbackSchedule.scheduled_time.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = session.scalar(stmt)
    if row is None:
        return None
    aid = _to_uuid(advisor_id) if advisor_id else None
    if row.assigned_advisor_id is None:
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


def _pick_advisor(session: Session, when: datetime,
                  index: ScheduleIndex | None = None) -> Advisor | None:
    """The least-loaded advisor actually working at ``when``; None when nobody is available.

    A booking is a promise that a specific person calls, so the promise must carry a name from
    the start - "an advisor will call you" has failed this caller before. Load counts OPEN
    callbacks assigned to each advisor for that whole business day, so the queue does not pile
    everything onto the first advisor whose shift covers the instant; the str(id) tie-break
    keeps the pick deterministic for tests and reports.
    """
    index = index or load_schedule(session)
    candidates = index.available_advisors(when)
    if not candidates:
        return None

    # Day-level load is the tie-break, but it cannot arbitrate the instant itself: an advisor
    # already booked at this exact minute cannot take a second caller then, however light the
    # rest of their day looks. This is also what makes the `remaining` count truthful - without
    # it the last free unit of capacity may belong to somebody already on the phone.
    taken_now = set(session.scalars(
        select(CallbackSchedule.assigned_advisor_id).where(
            CallbackSchedule.status == OPEN,
            CallbackSchedule.scheduled_time == when,
            CallbackSchedule.assigned_advisor_id.is_not(None),
        )
    ))
    candidates = [a for a in candidates if a.id not in taken_now]
    if not candidates:
        return None

    day_start = when.astimezone(BUSINESS_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    loads = dict(session.execute(
        select(CallbackSchedule.assigned_advisor_id, func.count())
        .where(CallbackSchedule.status == OPEN,
               CallbackSchedule.assigned_advisor_id.is_not(None),
               CallbackSchedule.scheduled_time >= day_start.astimezone(UTC),
               CallbackSchedule.scheduled_time < day_end.astimezone(UTC))
        .group_by(CallbackSchedule.assigned_advisor_id)
    ).all())
    return min(candidates, key=lambda a: (loads.get(a.id, 0), str(a.id)))


def reserve(session: Session, *, slot_start: str, customer_id: str | None = None,
            subscription_id: str | None = None, session_id: str | None = None,
            preferred_window: str | None = None, reason: str | None = None,
            priority: int = 1) -> dict | None:
    """Book one slot atomically. None when the slot filled up in the meantime.

    Two callers can reach the same slot in the same second, so capacity is re-checked under a
    transaction-scoped advisory lock: overbooking a callback is exactly as harmful as
    transferring two callers to one advisor.
    """
    from persistence.util import to_uuid

    try:
        when = datetime.fromisoformat(slot_start)
    except ValueError:
        return None
    when = when if when.tzinfo is not None else when.replace(tzinfo=UTC)

    # Slot-grid contract: everything the queue offers is minute-aligned on the grid, so a
    # reservation off it can only come from a hand-built payload, and honouring it would store a
    # timestamp no offer or report can ever produce. Refuse BEFORE the advisory lock: the lock is
    # for race-safe capacity checks, not for validating the caller's arithmetic.
    if when.minute % SLOT_MINUTES or when.second or when.microsecond:
        logger.info("callback refused: %s is off the %d-minute grid",
                    when.isoformat(), SLOT_MINUTES)
        return None

    session.execute(text("SELECT pg_advisory_xact_lock(hashtext('callback_slot_booking'))"))

    # Capacity is re-derived for THIS instant under the lock: the schedule may have been edited
    # between the offer and the answer, and a booking outside working hours is a call nobody makes.
    index = load_schedule(session)
    capacity = index.capacity_at(when)
    if capacity <= 0:
        logger.info("callback refused: no advisor works at %s", when.isoformat())
        return None
    used = session.scalar(
        select(func.count()).select_from(CallbackSchedule)
        .where(CallbackSchedule.status == OPEN, CallbackSchedule.scheduled_time == when)
    ) or 0
    if int(used) >= capacity:
        return None
    advisor = _pick_advisor(session, when, index=index)
    if advisor is None:
        logger.info("callback refused: no advisor available at %s", when.isoformat())
        return None

    row = CallbackSchedule(
        session_id=to_uuid(session_id),
        customer_id=to_uuid(customer_id),
        subscription_id=to_uuid(subscription_id),
        scheduled_time=when,
        priority_level=priority,
        assigned_advisor_id=advisor.id,
        preferred_window=(preferred_window or "")[:120] or None,
        reason=(reason or "")[:60] or None,
    )
    session.add(row)
    session.flush()
    logger.info("callback reserved for %s (customer=%s)", when.isoformat(), customer_id)
    return _hydrate(session, [row])[0]
