"""When the API confirms the time the caller asked for, it must be booked - not re-offered.

This is the exact regression the v71 patch introduced: the anti-hallucination guard rejected the
very instant the business API had just validated.
"""
import types

import pytest

from tasks.callback_schedule_task import CallbackScheduleTask


class _FakeClient:
    """Records what was reserved so the test asserts on the effect, not on the calls."""

    def __init__(self, confirmed: str) -> None:
        self.confirmed = confirmed
        self.reserved_with = None

    async def check_time(self, requested: str) -> dict:
        return dict(available=True, reason="ok", slot_start=self.confirmed,
                    slot_minutes=30, remaining=2, local_day="2026-08-03",
                    local_time="14:00", alternatives=[])

    async def reserve(self, slot_start: str, **kwargs) -> dict:
        self.reserved_with = slot_start
        return dict(id="cb-1", scheduled_time=slot_start)

    async def free_slots(self, **kwargs) -> list:
        return []


class _FakeSession:
    """Minimal LiveKit session so the task reaches the booking guard without an agent."""

    def __init__(self) -> None:
        self.userdata = types.SimpleNamespace(language="fr")

    async def say(self, text: str, allow_interruptions: bool = True) -> None:
        pass


@pytest.mark.asyncio
async def test_confirmed_counter_proposal_is_booked(monkeypatch):
    confirmed = "2026-08-03T13:00:00+00:00"
    client = _FakeClient(confirmed)
    monkeypatch.setattr("tasks.callback_schedule_task.get_callback_client", lambda: client)

    task = CallbackScheduleTask()
    task._activity = types.SimpleNamespace(session=_FakeSession())
    # Two slots were offered earlier; the caller asks for a third, different time.
    task._slots = [dict(slot_start="2026-08-03T09:00:00+00:00"),
                   dict(slot_start="2026-08-03T09:30:00+00:00")]

    await task.request_other_time(None, "le 3 aout a 14h")

    assert client.reserved_with == confirmed, (
        "the confirmed instant must reach reserve(); if this is None the _match guard "
        "rejected it and the agent silently re-offered the old slots"
    )
