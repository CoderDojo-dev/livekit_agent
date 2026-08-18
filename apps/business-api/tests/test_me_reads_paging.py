"""Paging contract tests for the portal read projections.

These exist because version_94 shipped notifications() and callbacks() that
reported an offset in the envelope and never applied it to the query. Every
test here fetches two different pages and compares rows: a test that only
asserts "the parameter is accepted" passes on that bug.
"""
from __future__ import annotations

import pytest
from business_api import me_reads


def _rows(payload: dict) -> list[tuple]:
    """Identity of a row, independent of key order."""
    return [tuple(sorted(item.items(), key=lambda kv: kv[0])) for item in payload["items"]]


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_pages_do_not_overlap(db_session, seeded_customer_id, reader):
    """Page 2 must not repeat page 1. This is the version_94 regression."""
    first = reader(db_session, customer_id=seeded_customer_id, limit=2, offset=0)
    second = reader(db_session, customer_id=seeded_customer_id, limit=2, offset=2)

    if first["total"] < 4:
        pytest.skip("seed does not have enough rows for this projection")

    assert set(_rows(first)).isdisjoint(set(_rows(second)))


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_walking_pages_yields_every_row_exactly_once(db_session, seeded_customer_id, reader):
    """A total order plus a correct offset means the union of the pages is the
    whole set, with no duplicates and nothing skipped."""
    total = reader(db_session, customer_id=seeded_customer_id, limit=1, offset=0)["total"]
    seen: list[tuple] = []
    for offset in range(0, total, 3):
        seen.extend(_rows(reader(db_session, customer_id=seeded_customer_id, limit=3, offset=offset)))

    assert len(seen) == total
    assert len(set(seen)) == total


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_total_is_independent_of_the_page(db_session, seeded_customer_id, reader):
    """total counts the set, not the window."""
    a = reader(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    b = reader(db_session, customer_id=seeded_customer_id, limit=50, offset=0)
    assert a["total"] == b["total"]


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_envelope_echoes_the_window_it_applied(db_session, seeded_customer_id, reader):
    payload = reader(db_session, customer_id=seeded_customer_id, limit=5, offset=5)
    assert payload["limit"] == 5
    assert payload["offset"] == 5
    assert len(payload["items"]) <= 5


def test_offset_beyond_the_end_is_empty_not_an_error(db_session, seeded_customer_id):
    payload = me_reads.notifications(
        db_session, customer_id=seeded_customer_id, limit=5, offset=10_000
    )
    assert payload["items"] == []
    assert payload["total"] > 0


def test_limit_is_clamped_to_page_max(db_session, seeded_customer_id):
    payload = me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=10_000, offset=0)
    assert payload["limit"] == me_reads._PAGE_MAX


def test_negative_offset_is_treated_as_zero(db_session, seeded_customer_id):
    payload = me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=5, offset=-20)
    assert payload["offset"] == 0


def test_billing_totals_do_not_follow_the_invoice_page(db_session, seeded_customer_id):
    """total_outstanding and next_due_date are account-wide (CB9, CB12 12.2)."""
    page_one = me_reads.billing(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    page_two = me_reads.billing(db_session, customer_id=seeded_customer_id, limit=1, offset=1)

    assert page_one["total_outstanding"] == page_two["total_outstanding"]
    assert page_one["next_due_date"] == page_two["next_due_date"]
    assert page_one["invoices"]["total"] == page_two["invoices"]["total"]
    if page_one["invoices"]["total"] > 1:
        assert page_one["invoices"]["items"] != page_two["invoices"]["items"]


def test_conversation_turns_are_chronological(db_session, seeded_customer_id):
    """CB8.4: turn_index asc, then created_at asc, is the sort order."""
    listing = me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=50, offset=0)
    for summary in listing["items"]:
        detail = me_reads.conversation_detail(
            db_session,
            customer_id=seeded_customer_id,
            session_id=summary["session_id"],
        )
        if detail is None or len(detail["turns"]) < 2:
            continue
        stamps = [turn["at"] for turn in detail["turns"] if turn["at"]]
        assert stamps == sorted(stamps)
        return
    pytest.skip("no seeded conversation with two or more turns")
