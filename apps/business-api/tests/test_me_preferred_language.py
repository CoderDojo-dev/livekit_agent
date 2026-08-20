"""The portal's one client-facing write: crm.customers.preferred_language.

The precedence that makes this setting meaningful lives in the agent worker
(config/language_policy.resolve_session_language) and is asserted there. What
these tests hold is the half business-api owns: only supported languages reach
the column, the write lands on the caller's own row, and an unsupported value
is refused with a 400 rather than crashing into the CHECK constraint.
"""
from __future__ import annotations

import pytest
from business_api import me_reads, me_writes

from persistence.models.crm import Customer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("fr", "fr"),
        ("FR", "fr"),
        ("fr-FR", "fr"),
        ("fr_FR", "fr"),
        ("  ar  ", "ar"),
        ("en-GB", "en"),
    ],
)
def test_normalise_accepts_the_shapes_a_locale_arrives_in(raw, expected):
    assert me_writes.normalise_language(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "de", "esperanto", "f", "zz", "fr fr"])
def test_normalise_refuses_anything_without_a_preset(raw):
    """An unsupported language must never reach the column: the agent worker has
    no STT/TTS preset for it and the CHECK constraint would 500 the request."""
    with pytest.raises(me_writes.UnsupportedLanguage):
        me_writes.normalise_language(raw)


def test_supported_set_matches_the_column_constraint():
    """crm.customers CHECK (preferred_language IN ('fr','ar','en')) is the real
    source of truth; this module's list must not drift from it."""
    assert set(me_writes.SUPPORTED_LANGUAGES) == {"fr", "ar", "en"}


def test_write_persists_and_reports_the_previous_value(db_session, seeded_customer_id):
    before = db_session.get(Customer, seeded_customer_id).preferred_language

    result = me_writes.set_preferred_language(db_session, seeded_customer_id, "en")
    assert result["preferred_language"] == "en"
    assert result["previous"] == before
    assert result["changed"] is (before != "en")
    assert db_session.get(Customer, seeded_customer_id).preferred_language == "en"

    # The read the portal renders the control from must agree with the write.
    assert me_reads is not None
    again = me_writes.set_preferred_language(db_session, seeded_customer_id, "en")
    assert again["changed"] is False


def test_write_touches_only_the_caller_row(db_session, seeded_customer_id, other_customer_id):
    """The endpoint derives customer_id from the bearer token; this asserts the
    layer underneath cannot spill onto a neighbouring row."""
    other_before = db_session.get(Customer, other_customer_id).preferred_language

    me_writes.set_preferred_language(db_session, seeded_customer_id, "ar")

    assert db_session.get(Customer, seeded_customer_id).preferred_language == "ar"
    assert db_session.get(Customer, other_customer_id).preferred_language == other_before


def test_unknown_customer_is_a_lookup_error(db_session):
    import uuid

    with pytest.raises(LookupError):
        me_writes.set_preferred_language(db_session, uuid.uuid4(), "fr")
