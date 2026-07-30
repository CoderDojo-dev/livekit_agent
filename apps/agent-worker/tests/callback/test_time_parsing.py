from datetime import datetime
from zoneinfo import ZoneInfo

from tasks.callback_schedule_task import parse_requested_time

TZ = ZoneInfo("Africa/Tunis")
NOW = datetime(2026, 7, 30, 10, 0, tzinfo=TZ)   # Thursday


def test_tomorrow_with_clock():
    assert parse_requested_time("demain a 14h", NOW).startswith("2026-07-31T14:00")


def test_explicit_date():
    assert parse_requested_time("le 31/07 vers 9h", NOW).startswith("2026-07-31T09:00")


def test_weekday_word_moves_forward():
    assert parse_requested_time("lundi matin", NOW).startswith("2026-08-03T09:00")


def test_part_of_day_only():
    assert parse_requested_time("demain apres-midi", NOW).startswith("2026-07-31T15:00")


def test_unparsable_returns_none():
    assert parse_requested_time("quand vous voulez", NOW) is None
