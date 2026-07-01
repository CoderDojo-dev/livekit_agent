"""context-service entrypoint (spec section 4): Customer-360, identity resolve/verify, read paths.

Backed by PostgreSQL via the shared persistence package. Endpoints are sync `def` so FastAPI
runs them in a threadpool (DB calls never block the event loop).
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Depends
from service_auth import require_internal_key
from sqlalchemy.orm import Session

from context_service.repositories import CrmRepository
from context_service.schemas import (
    Balance,
    Customer360,
    InvoiceListResponse,
    ResolveIdentityResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from persistence import get_session

app = FastAPI(title="context-service", dependencies=[Depends(require_internal_key)])


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/internal/context/resolve", response_model=ResolveIdentityResponse)
def resolve_identity(msisdn: str, session: Session = Depends(get_session)) -> ResolveIdentityResponse:
    """Resolve a caller MSISDN to canonical UUIDs (spec section 16.2) — the only place this happens."""
    resolved = CrmRepository(session).resolve_identity(msisdn)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no active subscription for msisdn")
    customer, subscription = resolved
    return ResolveIdentityResponse(
        customer_id=str(customer.id),
        subscription_id=str(subscription.id),
        preferred_language=customer.preferred_language,
    )


@app.get("/context/{msisdn}", response_model=Customer360)
def get_context(msisdn: str, session: Session = Depends(get_session)) -> Customer360:
    """Return the Customer-360 snapshot for a caller MSISDN (404 if unknown)."""
    snapshot = CrmRepository(session).build_customer360(msisdn)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="caller not found")
    return snapshot


@app.post("/verify-identity", response_model=VerifyIdentityResponse)
def verify_identity(
    req: VerifyIdentityRequest, session: Session = Depends(get_session)
) -> VerifyIdentityResponse:
    """Check a step-up identity answer server-side; the secret never leaves this service."""
    return VerifyIdentityResponse(verified=CrmRepository(session).verify_identity(req.customer_id, req.answer))


@app.get("/billing/{customer_id}/invoices", response_model=InvoiceListResponse)
def get_invoices(customer_id: str, session: Session = Depends(get_session)) -> InvoiceListResponse:
    """Return the customer's invoices (read-only consultation, CDC section 5.1)."""
    return InvoiceListResponse(invoices=CrmRepository(session).get_invoices(customer_id))


@app.get("/balance/{customer_id}", response_model=Balance)
def get_balance(customer_id: str, session: Session = Depends(get_session)) -> Balance:
    """Return the customer's prepaid balance (404 if none on file)."""
    balance = CrmRepository(session).get_balance(customer_id)
    if balance is None:
        raise HTTPException(status_code=404, detail="no balance on file")
    return balance