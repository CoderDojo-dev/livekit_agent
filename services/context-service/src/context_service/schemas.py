"""Wire DTOs for Customer-360, identity, invoices, and balances."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Customer360(BaseModel):
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
    customer_id: str
    subscription_id: str
    preferred_language: str = "fr"


class VerifyIdentityRequest(BaseModel):
    customer_id: str
    call_session_id: str
    answer: str


class VerifyIdentityResponse(BaseModel):
    verified: bool
    status: str
    reason: str | None = None
    verification_session_id: str | None = None
    verified_customer_id: str | None = None
    verification_level: str | None = None
    verification_method: str | None = None
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    attempt_count: int = 0


class Invoice(BaseModel):
    invoice_id: str
    amount: float
    currency: str = "TND"
    due_date: str
    status: str


class InvoiceListResponse(BaseModel):
    invoices: list[Invoice]


class Balance(BaseModel):
    customer_id: str
    credit: float
    currency: str = "TND"
    data_remaining_mb: int = 0
    valid_until: str | None = None
