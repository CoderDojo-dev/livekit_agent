"""Wire DTOs for the context-service (spec section 4). English-only system layer.

Backward compatible with the pre-persistence contract; adds subscription_id + fraud_suspected
(the canonical identity model, spec section 1).
"""
from __future__ import annotations

from pydantic import BaseModel


class Customer360(BaseModel):
    """The caller snapshot pre-fetched into session user-data at call start. Never carries PII secrets."""

    customer_id: str
    subscription_id: str | None = None
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0
    open_invoice_count: int = 0
    balance_summary: str | None = None


class ResolveIdentityResponse(BaseModel):
    """MSISDN -> canonical UUIDs (spec section 16.2). The only place this translation happens."""

    customer_id: str
    subscription_id: str
    preferred_language: str = "fr"


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