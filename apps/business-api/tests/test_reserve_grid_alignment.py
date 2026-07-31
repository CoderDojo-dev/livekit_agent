"""A reservation is a slot-grid contract: minute-aligned, zero sub-minute components.
A reserve() that silently accepts 13:07 stores a timestamp no offer or report can ever produce."""
from business_api.callbacks import reserve
from conftest import make_advisor, monday_slot


def test_reserve_refuses_a_minute_off_the_grid(db_session):
    make_advisor(db_session, name="Grid Guard")

    result = reserve(db_session, slot_start=monday_slot(13, 7).isoformat(),
                     reason="smoke-test")

    assert result is None, "13:07 is not on the 30-minute grid and must be refused"


def test_reserve_refuses_sub_minute_components(db_session):
    make_advisor(db_session, name="Grid Guard")

    result = reserve(db_session, slot_start=monday_slot(13, 0).replace(second=30).isoformat(),
                     reason="smoke-test")

    assert result is None, "a slot with seconds is not on the grid and must be refused"