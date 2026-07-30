from datetime import UTC, datetime, timedelta

from business_api.availability import ScheduleIndex, hhmm_to_minutes, minutes_to_hhmm


class _Advisor:
    def __init__(self, aid, language="fr", skills="general"):
        self.id, self.language, self.skills = aid, language, skills


class _Shift:
    def __init__(self, advisor_id, weekday, start, end, is_active=True):
        self.advisor_id, self.weekday = advisor_id, weekday
        self.start_minute, self.end_minute, self.is_active = start, end, is_active


class _Off:
    def __init__(self, advisor_id, starts_at, ends_at):
        self.advisor_id, self.starts_at, self.ends_at = advisor_id, starts_at, ends_at


def test_hhmm_round_trip():
    assert minutes_to_hhmm(hhmm_to_minutes("08:30")) == "08:30"


def test_slot_inside_shift_is_available():
    # Monday 2026-08-03 at 09:00 Tunis == 08:00 UTC
    index = ScheduleIndex([_Advisor("a")], [_Shift("a", 0, 480, 960)], [])
    assert index.capacity_at(datetime(2026, 8, 3, 8, 0, tzinfo=UTC)) == 1


def test_slot_outside_shift_is_closed():
    index = ScheduleIndex([_Advisor("a")], [_Shift("a", 0, 480, 960)], [])
    # Sunday, same hour
    assert index.capacity_at(datetime(2026, 8, 2, 8, 0, tzinfo=UTC)) == 0


def test_time_off_removes_the_advisor():
    moment = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    index = ScheduleIndex(
        [_Advisor("a")], [_Shift("a", 0, 480, 960)],
        [_Off("a", moment - timedelta(hours=1), moment + timedelta(hours=1))],
    )
    assert index.capacity_at(moment) == 0


def test_inactive_shift_is_ignored():
    index = ScheduleIndex([_Advisor("a")], [_Shift("a", 0, 480, 960, is_active=False)], [])
    assert index.capacity_at(datetime(2026, 8, 3, 8, 0, tzinfo=UTC)) == 0
