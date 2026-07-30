"""Advisor working hours: the rule that turns a registry into a real schedule.

Capacity used to be a single number - how many advisors are on call - which made every slot of
every day identical and left the agent unable to ever say "not that time". Here capacity becomes a
function of the instant asked about: an advisor counts for a slot only if a weekly shift covers it
and no dated exception removes them from it.

Everything is computed in memory from two small tables loaded once. Asking the database per slot
would mean sixty round-trips to answer a single "what have you got tomorrow?" - unacceptable inside
a voice turn, where the caller hears every millisecond.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.routing import Advisor, AdvisorShift, AdvisorTimeOff

logger = logging.getLogger(__name__)

# Shifts are written by humans in local time ("Monday 08:00"); slots are stored in UTC.
# Doing the conversion in one documented place is what keeps the two from drifting in October.
BUSINESS_TZ = ZoneInfo(os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis"))

WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday",
                 "friday", "saturday", "sunday")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def minutes_to_hhmm(minutes: int) -> str:
    """960 -> '16:00'. The dashboard renders this directly; the agent never sees it."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hhmm_to_minutes(value: str) -> int:
    """'16:00' -> 960. Raises ValueError on anything else, so a bad payload is a 400, not a hole."""
    hours, _, mins = value.partition(":")
    total = int(hours) * 60 + int(mins or 0)
    if not 0 <= total <= 1440:
        raise ValueError(f"time out of range: {value!r}")
    return total


class ScheduleIndex:
    """An in-memory snapshot of who works when, built once and queried per slot.

    Built from three cheap queries; answering 'is advisor X available at T' is then pure
    arithmetic. This is what lets free_slots stay a single database round-trip.
    """

    def __init__(self, advisors: list[Advisor], shifts: list[AdvisorShift],
                 time_off: list[AdvisorTimeOff]) -> None:
        self.advisors = {a.id: a for a in advisors}
        self._shifts: dict[object, list[tuple[int, int, int]]] = {}
        for shift in shifts:
            if shift.is_active and shift.advisor_id in self.advisors:
                self._shifts.setdefault(shift.advisor_id, []).append(
                    (shift.weekday, shift.start_minute, shift.end_minute)
                )
        self._time_off: dict[object, list[tuple[datetime, datetime]]] = {}
        for off in time_off:
            self._time_off.setdefault(off.advisor_id, []).append(
                (_aware(off.starts_at), _aware(off.ends_at))
            )

    def is_available(self, advisor_id, moment: datetime) -> bool:
        """True when a weekly shift covers ``moment`` and no exception removes it."""
        local = _aware(moment).astimezone(BUSINESS_TZ)
        minute_of_day = local.hour * 60 + local.minute
        windows = self._shifts.get(advisor_id, ())
        covered = any(
            weekday == local.weekday() and start <= minute_of_day < end
            for weekday, start, end in windows
        )
        if not covered:
            return False
        moment = _aware(moment)
        return not any(start <= moment < end for start, end in self._time_off.get(advisor_id, ()))

    def available_advisors(self, moment: datetime) -> list[Advisor]:
        return [a for aid, a in self.advisors.items() if self.is_available(aid, moment)]

    def capacity_at(self, moment: datetime) -> int:
        """How many callbacks this instant can hold, before subtracting existing bookings."""
        return sum(1 for aid in self.advisors if self.is_available(aid, moment))


def load_schedule(session: Session, skill_tag: str | None = None,
                  language: str | None = None) -> ScheduleIndex:
    """Load the schedule of every bookable advisor, optionally narrowed to a skill or language.

    Narrowing is what will later let the agent say "our English-speaking advisor can call you
    Tuesday": the same index, a different filter. Nothing else in the chain changes.
    """
    stmt = select(Advisor).where(Advisor.is_active.is_(True), Advisor.is_on_call.is_(True))
    if language:
        stmt = stmt.where(Advisor.language == language)
    advisors = list(session.scalars(stmt))
    if skill_tag:
        wanted = skill_tag.strip().lower()
        advisors = [
            a for a in advisors
            if wanted in {s.strip().lower() for s in (a.skills or "").split(",")}
            or "general" in {s.strip().lower() for s in (a.skills or "").split(",")}
        ]
    if not advisors:
        return ScheduleIndex([], [], [])

    ids = [a.id for a in advisors]
    shifts = list(session.scalars(
        select(AdvisorShift).where(AdvisorShift.advisor_id.in_(ids))
    ))
    horizon = datetime.now(UTC) + timedelta(days=30)
    time_off = list(session.scalars(
        select(AdvisorTimeOff).where(
            AdvisorTimeOff.advisor_id.in_(ids),
            AdvisorTimeOff.ends_at >= datetime.now(UTC),
            AdvisorTimeOff.starts_at <= horizon,
        )
    ))
    return ScheduleIndex(advisors, shifts, time_off)


# ---------------- shift CRUD (admin dashboard) ----------------
def shift_to_dict(shift: AdvisorShift) -> dict:
    return {
        "id": str(shift.id),
        "advisor_id": str(shift.advisor_id),
        "weekday": shift.weekday,
        "weekday_name": WEEKDAY_NAMES[shift.weekday],
        "start": minutes_to_hhmm(shift.start_minute),
        "end": minutes_to_hhmm(shift.end_minute),
        "is_active": shift.is_active,
    }


def list_shifts(session: Session, advisor_id: str) -> list[dict]:
    from persistence.util import to_uuid

    aid = to_uuid(advisor_id)
    if aid is None:
        return []
    rows = session.scalars(
        select(AdvisorShift).where(AdvisorShift.advisor_id == aid)
        .order_by(AdvisorShift.weekday.asc(), AdvisorShift.start_minute.asc())
    )
    return [shift_to_dict(r) for r in rows]


def replace_shifts(session: Session, advisor_id: str, windows: list[dict]) -> list[dict]:
    """Replace an advisor's whole weekly grid in one transaction.

    A schedule editor sends the grid it shows, not a stream of deltas: replacing wholesale is the
    only way the saved state can be guaranteed identical to what the admin was looking at. Overlaps
    are rejected rather than merged, because two overlapping windows would silently double that
    advisor's capacity for the overlapping hour.
    """
    from persistence.util import to_uuid

    aid = to_uuid(advisor_id)
    if aid is None or session.get(Advisor, aid) is None:
        raise LookupError("advisor not found")

    parsed: list[tuple[int, int, int, bool]] = []
    for window in windows:
        weekday = int(window["weekday"])
        if not 0 <= weekday <= 6:
            raise ValueError(f"weekday must be 0..6, got {weekday}")
        start = hhmm_to_minutes(str(window["start"]))
        end = hhmm_to_minutes(str(window["end"]))
        if end <= start:
            raise ValueError(f"end must be after start for weekday {weekday}")
        parsed.append((weekday, start, end, bool(window.get("is_active", True))))

    for day in range(7):
        day_windows = sorted((w for w in parsed if w[0] == day), key=lambda w: w[1])
        for earlier, later in zip(day_windows, day_windows[1:]):
            if later[1] < earlier[2]:
                raise ValueError(f"overlapping windows on weekday {day}")

    for existing in session.scalars(select(AdvisorShift).where(AdvisorShift.advisor_id == aid)):
        session.delete(existing)
    session.flush()

    for weekday, start, end, is_active in parsed:
        session.add(AdvisorShift(advisor_id=aid, weekday=weekday, start_minute=start,
                                 end_minute=end, is_active=is_active))
    session.flush()
    logger.info("schedule replaced for advisor %s (%d windows)", advisor_id, len(parsed))
    return list_shifts(session, advisor_id)


# ---------------- time off ----------------
def time_off_to_dict(row: AdvisorTimeOff) -> dict:
    return {
        "id": str(row.id),
        "advisor_id": str(row.advisor_id),
        "starts_at": _aware(row.starts_at).isoformat(),
        "ends_at": _aware(row.ends_at).isoformat(),
        "reason": row.reason,
    }


def list_time_off(session: Session, advisor_id: str | None = None,
                  upcoming_only: bool = True) -> list[dict]:
    from persistence.util import to_uuid

    stmt = select(AdvisorTimeOff).order_by(AdvisorTimeOff.starts_at.asc())
    if advisor_id:
        aid = to_uuid(advisor_id)
        if aid is None:
            return []
        stmt = stmt.where(AdvisorTimeOff.advisor_id == aid)
    if upcoming_only:
        stmt = stmt.where(AdvisorTimeOff.ends_at >= datetime.now(UTC))
    return [time_off_to_dict(r) for r in session.scalars(stmt)]


def create_time_off(session: Session, advisor_id: str, starts_at: str, ends_at: str,
                    reason: str | None = None) -> dict:
    from persistence.util import to_uuid

    aid = to_uuid(advisor_id)
    if aid is None or session.get(Advisor, aid) is None:
        raise LookupError("advisor not found")
    start = _aware(datetime.fromisoformat(starts_at))
    end = _aware(datetime.fromisoformat(ends_at))
    if end <= start:
        raise ValueError("ends_at must be after starts_at")
    row = AdvisorTimeOff(advisor_id=aid, starts_at=start, ends_at=end,
                         reason=(reason or "")[:120] or None)
    session.add(row)
    session.flush()
    return time_off_to_dict(row)


def delete_time_off(session: Session, time_off_id: str) -> bool:
    from persistence.util import to_uuid

    tid = to_uuid(time_off_id)
    row = session.get(AdvisorTimeOff, tid) if tid else None
    if row is None:
        return False
    session.delete(row)
    return True


# ---------------- supervision ----------------
def coverage_report(session: Session, days: int = 7) -> dict:
    """Hour-by-hour coverage for the next ``days`` - the view a supervisor actually needs.

    Reading seven weekly grids and mentally subtracting three leaves is not supervision. This
    returns the answer directly, including the hours nobody covers, which is the only number that
    predicts a callback the queue cannot honour.
    """
    index = load_schedule(session)
    now = datetime.now(UTC)
    start = now.astimezone(BUSINESS_TZ).replace(minute=0, second=0, microsecond=0)
    rows: list[dict] = []
    gaps: list[str] = []
    cursor = start
    limit = start + timedelta(days=days)
    while cursor < limit:
        local_hour = cursor.hour
        if 8 <= local_hour < 20:
            available = index.available_advisors(cursor)
            entry = {
                "at": cursor.astimezone(UTC).isoformat(),
                "local": cursor.strftime("%Y-%m-%d %H:%M"),
                "advisors": len(available),
                "languages": sorted({a.language for a in available}),
            }
            rows.append(entry)
            if not available:
                gaps.append(entry["local"])
        cursor += timedelta(hours=1)
    return {
        "hours": rows,
        "uncovered_hours": gaps,
        "advisors_total": len(index.advisors),
        "timezone": str(BUSINESS_TZ),
    }


def advisor_week(session: Session, advisor_id: str) -> dict:
    """One advisor's weekly grid plus their upcoming absences - the dashboard detail panel."""
    return {
        "advisor_id": advisor_id,
        "shifts": list_shifts(session, advisor_id),
        "time_off": list_time_off(session, advisor_id),
        "timezone": str(BUSINESS_TZ),
    }
