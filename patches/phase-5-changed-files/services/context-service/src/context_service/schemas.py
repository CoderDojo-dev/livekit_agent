"""Wire DTOs for the context-service (Blueprint section 4.3). English-only system layer."""
from __future__ import annotations

from pydantic import BaseModel


class Customer360(BaseModel):
    """The caller snapshot pre-fetched into session user-data at call start.

    Never carries the identity secret. Invoice/balance counts enriched in Phase 5.
    """

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: str = "fr"
    is_vip: bool = False
    account_age_days: int = 0
    open_invoice_count: int = 0
    balance_summary: str | None = None


class VerifyIdentityRequest(BaseModel):
    """Step-up identity check input (CDC section 6.5). The secret never leaves the service."""

    customer_id: str
    answer: str


class VerifyIdentityResponse(BaseModel):
    """Step-up identity check result."""

    verified: bool


class Invoice(BaseModel):
    """A single invoice (read-only consultation, CDC section 5.1)."""

    invoice_id: str
    amount: float
    currency: str = "TND"
    due_date: str
    status: str  # "open" | "paid" | "overdue"


class InvoiceListResponse(BaseModel):
    """Open invoices for a customer."""

    invoices: list[Invoice]


class Balance(BaseModel):
    """Prepaid credit / data balance (read-only, CDC section 5.x)."""

    customer_id: str
    credit: float
    currency: str = "TND"
    data_remaining_mb: int = 0
    valid_until: str | None = None