"""Provisioning / SIM lifecycle simulator service (dev-only, but a REAL ledger).

Implements the contract LiveProvisioningAdapter calls, so the platform runs in CONNECTOR_MODE=live
against this service with no code change - and in production the same adapter points at the
carrier's provisioning system by swapping PROVISIONING_ADAPTER_URL.

Endpoints are declared `def`, not `async def`: the ledger uses the synchronous Postgres session,
and running blocking DB work inside an async endpoint would occupy the event loop and stall every
other request. FastAPI runs sync endpoints in a threadpool, so concurrent calls stay concurrent.

  POST /sim/unblock      {customer_id, idempotency_key}                -> {"reference": ...}
  POST /sim/reactivate   {customer_id, idempotency_key}                -> {"reference": ...}
  POST /sim/replace      {customer_id, sim_type, idempotency_key}      -> {"reference": ...}
  POST /sim/change-plan  {customer_id, plan_code, idempotency_key}     -> {"reference": ...}
  POST /sim/roaming      {customer_id, enable, idempotency_key}        -> {"reference": ...}
  GET  /subscription/{customer_id}                                     -> line state
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from persistence.engine import session_scope
from provisioning_sim import provisioning
from service_auth import require_internal_key

logger = logging.getLogger(__name__)
app = FastAPI(title="provisioning-sim", dependencies=[Depends(require_internal_key)])


class SimOp(BaseModel):
    customer_id: str
    idempotency_key: str


class ReplaceOp(BaseModel):
    customer_id: str
    sim_type: str = "physical"
    idempotency_key: str


class PlanOp(BaseModel):
    customer_id: str
    plan_code: str
    idempotency_key: str


class RoamingOp(BaseModel):
    customer_id: str
    enable: bool = True
    idempotency_key: str


def _run(operation, *args) -> dict:
    """Execute a ledger operation, mapping refusals to honest HTTP errors.

    A ProvisioningError is a business refusal (wrong line state, unknown plan, unknown customer),
    so it becomes a 404/409 the agent can explain - never a synthesized success.
    """
    try:
        with session_scope() as session:
            return {"reference": operation(session, *args)}
    except provisioning.ProvisioningError as exc:
        message = str(exc)
        code = (status.HTTP_404_NOT_FOUND
                if "no subscription" in message or "not a valid" in message
                else status.HTTP_409_CONFLICT)
        raise HTTPException(code, message)


@app.get("/health")
async def health() -> dict:
    """Liveness probe. Backed by the real subscription/SIM tables; no in-memory fallback."""
    return {"status": "ok", "service": "provisioning-sim", "backing": "postgres-provisioning"}


@app.get("/subscription/{customer_id}")
def subscription_state(customer_id: str) -> dict:
    try:
        with session_scope() as session:
            return provisioning.get_subscription_state(session, customer_id)
    except provisioning.ProvisioningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@app.post("/sim/unblock")
def sim_unblock(op: SimOp) -> dict:
    return _run(provisioning.unblock_sim, op.customer_id, op.idempotency_key)


@app.post("/sim/reactivate")
def sim_reactivate(op: SimOp) -> dict:
    return _run(provisioning.reactivate_sim, op.customer_id, op.idempotency_key)


@app.post("/sim/replace")
def sim_replace(op: ReplaceOp) -> dict:
    return _run(provisioning.replace_sim, op.customer_id, op.sim_type, op.idempotency_key)


@app.post("/sim/change-plan")
def plan_change(op: PlanOp) -> dict:
    return _run(provisioning.change_plan, op.customer_id, op.plan_code, op.idempotency_key)


@app.post("/sim/roaming")
def roaming(op: RoamingOp) -> dict:
    return _run(provisioning.set_roaming, op.customer_id, op.enable, op.idempotency_key)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8109")))


if __name__ == "__main__":
    run()
