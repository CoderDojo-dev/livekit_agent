"""Slot generation must respect business-local opening hours, not UTC ones."""
from datetime import UTC, datetime

from business_api.availability import BUSINESS_TZ, DAY_END_HOUR, DAY_START_HOUR
from business_api.callbacks import _slot_bounds


def test_every_generated_slot_is_within_local_business_hours():
    now = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)  # 05:00 in Tunis, before opening

    slots = _slot_bounds(now, days=2)

    assert slots, "a two-day window must contain bookable slots"
    for slot in slots:
        local_hour = slot.astimezone(BUSINESS_TZ).hour
        assert DAY_START_HOUR <= local_hour < DAY_END_HOUR, (
            f"{slot.isoformat()} is {local_hour}h local, outside business hours"
        )


def test_the_first_local_working_hour_is_offered():
    """08:00 local was silently dropped because 07:00 UTC failed the 8-hour test."""
    now = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)

    local_hours = {s.astimezone(BUSINESS_TZ).hour for s in _slot_bounds(now, days=1)}

    assert DAY_START_HOUR in local_hours
