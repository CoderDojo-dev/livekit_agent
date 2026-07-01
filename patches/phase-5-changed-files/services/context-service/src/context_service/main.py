"""context-service entrypoint (Blueprint section 4.3): Customer-360 + identity + read paths."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from context_service.aggregator import ContextAggregator
from context_service.schemas import (
    Balance,
    Customer360,
    InvoiceListResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)

app = FastAPI(title="context-service")
_aggregator = ContextAggregator()


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/context/{msisdn}", response_model=Customer360)
async def get_context(msisdn: str) -> Customer360:
    """Return the Customer-360 snapshot for a caller MSISDN (404 if unknown)."""
    snapshot = _aggregator.build_customer360(msisdn)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="caller not found")
    return snapshot


@app.post("/verify-identity", response_model=VerifyIdentityResponse)
async def verify_identity(req: VerifyIdentityRequest) -> VerifyIdentityResponse:
    """Check a step-up identity answer server-side; the secret never leaves this service."""
    return VerifyIdentityResponse(verified=_aggregator.verify_identity(req.customer_id, req.answer))


@app.get("/billing/{customer_id}/invoices", response_model=InvoiceListResponse)
async def get_invoices(customer_id: str) -> InvoiceListResponse:
    """Return the customer's invoices (read-only consultation, CDC section 5.1)."""
    return InvoiceListResponse(invoices=_aggregator.get_invoices(customer_id))


@app.get("/balance/{customer_id}", response_model=Balance)
async def get_balance(customer_id: str) -> Balance:
    """Return the customer's prepaid balance (404 if none on file)."""
    balance = _aggregator.get_balance(customer_id)
    if balance is None:
        raise HTTPException(status_code=404, detail="no balance on file")
    return balance