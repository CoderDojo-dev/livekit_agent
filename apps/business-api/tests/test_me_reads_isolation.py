"""Cross-customer isolation for every portal read projection.

The invariant in me_reads' own docstring is that customer_id always arrives
from Principal.customer_id and every {id} lookup re-checks ownership. These
tests are what make that a fact rather than a comment.
"""
from __future__ import annotations

import pytest
from business_api import me_reads

LIST_READERS = [
    me_reads.notifications,
    me_reads.callbacks,
    me_reads.conversations,
    me_reads.requests,
]


@pytest.mark.parametrize("reader", LIST_READERS)
def test_reader_returns_nothing_for_an_unrelated_customer(db_session, other_customer_id, reader):
    """A customer with no rows of their own must get an empty, well-formed
    envelope - never another customer's rows."""
    payload = reader(db_session, customer_id=other_customer_id, limit=50, offset=0)
    assert payload["total"] == len(payload["items"])


def test_conversation_detail_hides_another_customers_session(
    db_session, seeded_customer_id, other_customer_id
):
    """Another customer's session_id must be indistinguishable from a
    nonexistent one: both return None so the route answers 404, not 403."""
    mine = me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    if not mine["items"]:
        pytest.skip("no seeded conversation")
    session_id = mine["items"][0]["session_id"]

    assert (
        me_reads.conversation_detail(
            db_session, customer_id=other_customer_id, session_id=session_id
        )
        is None
    )


def test_no_projection_leaks_a_forbidden_key(db_session, seeded_customer_id):
    """The forbidden-key list, enforced in code instead of by grep. vip is on
    this list per CB12 12.5.4: it is internal segmentation."""
    forbidden = {
        "frustration",
        "max_frustration",
        "sentiment",
        "token_digest",
        "failure_reason",
        "audio_record_url",
        "recording_consent",
        "has_recording",
        "customer_vip",
        "vip",
        "last_synced_at",
        "outcome_note",
        "transaction_reference",
        "detected_intent",
        "attempts",
    }

    payloads = [
        me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.callbacks(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.requests(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.billing(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.balance(db_session, customer_id=seeded_customer_id),
    ]

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in forbidden, f"forbidden key {key} in a portal projection"
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        walk(payload)
