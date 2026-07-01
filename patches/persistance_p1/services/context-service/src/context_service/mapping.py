"""Pure mapping helpers (no DB) - unit-testable in isolation."""
from __future__ import annotations

import datetime


def invoice_status(raw: str) -> str:
    """Map a billing.invoices.status to the agent-facing open/paid/overdue vocabulary."""
    if raw == "paid":
        return "paid"
    if raw == "overdue":
        return "overdue"
    return "open"


def account_age_days(activation_date: datetime.date | None, today: datetime.date | None = None) -> int:
    """Derive account age in days from the subscription activation date."""
    if activation_date is None:
        return 0
    today = today or datetime.date.today()
    return max((today - activation_date).days, 0)


def verify_answer(national_id: str | None, answer: str) -> bool:
    """The step-up secret is the last 4 digits of the national id (CIN); compared server-side."""
    if not national_id:
        return False
    return answer.strip() == national_id[-4:]


def to_megabytes(value: float, unit: str) -> int:
    """Normalize a data balance to MB (GB->MB, MB as-is)."""
    if unit == "GB":
        return int(value * 1024)
    if unit == "MB":
        return int(value)
    return 0