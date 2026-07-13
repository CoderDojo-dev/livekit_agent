"""Customer-360, persisted identity verification, and billing read API."""
from __future__ import annotations

import os
from typing import Annotated

from cache import get_cache
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from context_service.auth_service import verify_cin_last4
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
from service_auth import require_internal_key
from observability_kit import configure_tracer, trace_requests

app = FastAPI(
    title="context-service",
    dependencies=[Depends(require_internal_key)],
)
configure_tracer("context-service")
trace_requests(app, "context-service")
_cache = get_cache()
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get(
    "/internal/context/resolve",
    response_model=ResolveIdentityResponse,
)
def resolve_identity(
    msisdn: str,
    session: DbSession,
) -> ResolveIdentityResponse:
    """Resolve trusted MSISDN to canonical customer/subscription IDs."""
    normalized = msisdn.strip()
    cache_key = f"ctx:resolve:{normalized}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return ResolveIdentityResponse.model_validate_json(cached)

    resolved = CrmRepository(session).resolve_identity(normalized)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail="no active subscription for msisdn",
        )

    customer, subscription = resolved
    response = ResolveIdentityResponse(
        customer_id=str(customer.id),
        subscription_id=str(subscription.id),
        preferred_language=customer.preferred_language,
    )
    _cache.set(
        cache_key,
        response.model_dump_json(),
        ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
    )
    return response


@app.get(
    "/context/{msisdn}",
    response_model=Customer360,
)
def get_context(
    msisdn: str,
    session: DbSession,
) -> Customer360:
    """Return Customer-360 for a trusted caller MSISDN."""
    snapshot = CrmRepository(session).build_customer360(msisdn.strip())
    if snapshot is None:
        raise HTTPException(status_code=404, detail="caller not found")
    return snapshot


@app.post(
    "/verify-identity",
    response_model=VerifyIdentityResponse,
)
def verify_identity(
    req: VerifyIdentityRequest,
    session: DbSession,
) -> VerifyIdentityResponse:
    """Persist and evaluate a customer-bound CIN verification attempt."""
    result = verify_cin_last4(
        session,
        customer_id=req.customer_id,
        call_session_id=req.call_session_id,
        answer=req.answer,
    )
    return VerifyIdentityResponse.model_validate(result)


@app.get(
    "/billing/{customer_id}/invoices",
    response_model=InvoiceListResponse,
)
def get_invoices(
    customer_id: str,
    session: DbSession,
) -> InvoiceListResponse:
    """Return customer invoices."""
    invoices = CrmRepository(session).get_invoices(customer_id)
    return InvoiceListResponse(invoices=invoices)


@app.get(
    "/balance/{customer_id}",
    response_model=Balance,
)
def get_balance(
    customer_id: str,
    session: DbSession,
) -> Balance:
    """Return prepaid balance."""
    balance = CrmRepository(session).get_balance(customer_id)
    if balance is None:
        raise HTTPException(
            status_code=404,
            detail="no balance on file",
        )
    return balance


def run() -> None:
    """Run context-service on port 8101."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101)
