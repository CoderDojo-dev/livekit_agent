"""A reservation must name a real, working advisor from the moment it is written.
An unassigned promise ("an advisor will call you") is what this queue was built to stop."""
from business_api.callbacks import reserve

from conftest import db_session, make_advisor, monday_slot  # noqa: F401


def test_reserve_names_a_working_advisor(db_session):
    from business_api.availability import load_schedule

    advisor = make_advisor(db_session, name="Amina Test")
    when = monday_slot(13, 0)

    result = reserve(db_session, slot_start=when.isoformat(), reason="smoke-test")

    assert result is not None, "a working advisor makes the slot bookable"
    assert result["assigned_advisor_id"] is not None, "the booking must carry an advisor"
    assert result["assigned_advisor_name"] is not None, "the booking must name the advisor"
    working_names = {a.full_name for a in load_schedule(db_session).available_advisors(when)}
    assert result["assigned_advisor_name"] in working_names, (
        "the named advisor must actually be working that slot, not a stale or made-up name"
    )


def test_two_bookings_at_same_hour_go_to_different_advisors(db_session):
    make_advisor(db_session, name="Test Advisor One")
    make_advisor(db_session, name="Test Advisor Two")

    first = reserve(db_session, slot_start=monday_slot(13, 0).isoformat(), reason="smoke-test")
    second = reserve(db_session, slot_start=monday_slot(13, 0).isoformat(), reason="smoke-test")

    assert first is not None and second is not None
    assert first["assigned_advisor_id"] != second["assigned_advisor_id"], (
        "least-loaded picking must spread the same hour across different advisors"
    )


def test_three_reservations_on_the_same_instant_refuse_the_third(db_session):
    """Day-level load is the tie-break, but it cannot arbitrate the instant itself:
    an advisor already booked at this exact minute cannot take a second caller then,
    however light the rest of their day looks (v74 §1)."""
    from persistence.models.conversation import CallbackSchedule
    from persistence.models.routing import AdvisorShift

    # Only the two test advisors may see the slot: production shifts (Monday 08:00-18:00
    # local) are still live rows, and "two advisors only" must mean a capacity of exactly two.
    db_session.execute(AdvisorShift.__table__.update()
                       .where(AdvisorShift.weekday == 0)
                       .values(is_active=False))
    busy = make_advisor(db_session, name="Chargé Ce Matin")
    free = make_advisor(db_session, name="Libre Ce Matin")
    when = monday_slot(13, 0)
    morning = monday_slot(9, 0)  # 10:00 local, both advisors on shift
    for _ in range(3):
        db_session.add(CallbackSchedule(
            scheduled_time=morning, status="pending",
            assigned_advisor_id=busy.id, priority_level=1,
        ))
    db_session.flush()

    first = reserve(db_session, slot_start=when.isoformat(), reason="smoke-test")
    second = reserve(db_session, slot_start=when.isoformat(), reason="smoke-test")
    third = reserve(db_session, slot_start=when.isoformat(), reason="smoke-test")

    assert first is not None and second is not None
    assert first["assigned_advisor_id"] != second["assigned_advisor_id"], (
        "an advisor already booked at this minute must not be booked again - "
        "day-level load alone would re-pick the least-loaded advisor twice"
    )
    assert third is None, "two advisors, three bookings on the same instant: the third must be refused"
