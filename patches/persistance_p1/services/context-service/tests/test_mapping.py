"""Offline unit tests for the pure mapping helpers (no DB). Repository reads are integration-tested
against Postgres on the developer machine (see the persistence README)."""
from __future__ import annotations

import datetime

from context_service import mapping


def test_invoice_status_mapping() -> None:
    assert mapping.invoice_status("paid") == "paid"
    assert mapping.invoice_status("overdue") == "overdue"
    assert mapping.invoice_status("issued") == "open"
    assert mapping.invoice_status("partial") == "open"


def test_account_age_days() -> None:
    today = datetime.date(2026, 6, 29)
    assert mapping.account_age_days(datetime.date(2026, 6, 29), today) == 0
    assert mapping.account_age_days(datetime.date(2026, 3, 31), today) == 90
    assert mapping.account_age_days(None, today) == 0


def test_verify_answer_uses_last4_of_national_id() -> None:
    assert mapping.verify_answer("11224087", "4087") is True
    assert mapping.verify_answer("11224087", " 4087 ") is True
    assert mapping.verify_answer("11224087", "1122") is False
    assert mapping.verify_answer(None, "4087") is False


def test_to_megabytes() -> None:
    assert mapping.to_megabytes(2, "GB") == 2048
    assert mapping.to_megabytes(1840, "MB") == 1840
    assert mapping.to_megabytes(5, "TND") == 0