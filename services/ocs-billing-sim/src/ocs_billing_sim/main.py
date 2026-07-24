"""OCS + Billing simulator service (dev-only, but a REAL ledger).

Implements the exact HTTP contract the LiveOcsAdapter and LiveBillingAdapter call, so the
platform runs in CONNECTOR_MODE=live against this service with no code change - and in production
the same adapters point at the carrier's OCS/billing by swapping OCS_ADAPTER_URL /
BILLING_ADAPTER_URL. Every write moves real money in the real domain tables; failures return
honest HTTP errors, never a fabricated reference.

Endpoints (adapter contract):
  GET  /balance/{customer_id}        -> balance projection
  POST /topup    {customer_id, amount, currency, idempotency_key}   -> {"reference": ...}
  POST /addon    {customer_id, addon_id, idempotency_key}
  GET  /invoices/{customer_id}       -> {"invoices": [...]}
  POST /charge   {customer_id, amount, currency, idempotency_key}   -> {"reference": ...}
  POST /deferral {customer_id, days, idempotency_key}
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from ocs_billing_sim import ledger
from persistence.engine import session_scope
from service_auth import require_internal_key

logger = logging.getLogger(__name__)
app = FastAPI(title="ocs-billing-sim", dependencies=[Depends(require_internal_key)])


class MoneyOp(BaseModel):
    customer_id: str
    amount: str
    currency: str = "TND"
    idempotency_key: str


class AddonOp(BaseModel):
    customer_id: str
    addon_id: str
    idempotency_key: str


class DeferralOp(BaseModel):
    customer_id: str
    days: int
    idempotency_key: str


def _amount(raw: str) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid amount {raw!r}") from None
    if value <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "amount must be positive")
    return value


@app.get("/health")
async def health() -> dict:
    """Liveness probe. This service requires a database - it has no in-memory fallback."""
    return {"status": "ok", "service": "ocs-billing-sim", "backing": "postgres-ledger"}


# ---------------- OCS ----------------
@app.get("/balance/{customer_id}")
def balance(customer_id: str) -> dict:
    try:
        with session_scope() as session:
            return ledger.get_balance(session, customer_id)
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/topup")
def topup(op: MoneyOp) -> dict:
    try:
        with session_scope() as session:
            reference = ledger.top_up(session, op.customer_id, _amount(op.amount),
                                      op.currency, op.idempotency_key)
        return {"reference": reference}
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/addon")
def addon(op: AddonOp) -> dict:
    try:
        with session_scope() as session:
            ledger.apply_data_addon(session, op.customer_id, op.addon_id, op.idempotency_key)
        return {"applied": True}
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ---------------- Billing ----------------
@app.get("/invoices/{customer_id}")
def invoices(customer_id: str) -> dict:
    try:
        with session_scope() as session:
            return {"invoices": ledger.get_invoices(session, customer_id)}
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/charge")
def charge(op: MoneyOp) -> dict:
    try:
        with session_scope() as session:
            reference = ledger.charge(session, op.customer_id, _amount(op.amount),
                                      op.currency, op.idempotency_key)
        return {"reference": reference}
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/deferral")
def deferral(op: DeferralOp) -> dict:
    try:
        with session_scope() as session:
            ledger.grant_deferral(session, op.customer_id, op.days, op.idempotency_key)
        return {"granted": True}
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


def run() -> None:
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8107")))


if __name__ == "__main__":
    run()
