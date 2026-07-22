"""FastAPI application for the SIM / provisioning simulator."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from provisioning_sim.provisioning import ProvisioningLedger

app = FastAPI(
    title="Provisioning SIM Simulator",
    version="0.1.0",
    description="In-memory SIM lifecycle / provisioning simulation (CDC section 5.4).",
)

ledger = ProvisioningLedger()

# ---- request / response models ---


class SimActivateRequest(BaseModel):
    msisdn: str
    iccid: str


class SimReplaceRequest(BaseModel):
    msisdn: str
    new_iccid: str


class ChangePlanRequest(BaseModel):
    msisdn: str
    new_plan_code: str


class SimOnlyRequest(BaseModel):
    msisdn: str


class SimResponse(BaseModel):
    reference: str
    msisdn: str
    iccid: str
    plan_code: str
    active: bool
    roaming_enabled: bool


# ---- endpoints ---


@app.post("/sim/activate")
async def activate_sim(body: SimActivateRequest) -> dict:
    ref = ledger.activate_sim(body.msisdn, body.iccid)
    return _sim_response(body.msisdn, ref)


@app.post("/sim/deactivate")
async def deactivate_sim(body: SimOnlyRequest) -> dict:
    try:
        ref = ledger.deactivate_sim(body.msisdn)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _sim_response(body.msisdn, ref)


@app.post("/sim/replace")
async def replace_sim(body: SimReplaceRequest) -> dict:
    try:
        ref = ledger.replace_sim(body.msisdn, body.new_iccid)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _sim_response(body.msisdn, ref)


@app.post("/sim/change-plan")
async def change_plan(body: ChangePlanRequest) -> dict:
    try:
        ref = ledger.change_plan(body.msisdn, body.new_plan_code)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _sim_response(body.msisdn, ref)


@app.post("/sim/activate-roaming")
async def activate_roaming(body: SimOnlyRequest) -> dict:
    try:
        ref = ledger.activate_roaming(body.msisdn)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _sim_response(body.msisdn, ref)


@app.get("/sim/{msisdn}")
async def get_sim(msisdn: str) -> dict:
    sim = ledger.get_sim(msisdn)
    if sim is None:
        raise HTTPException(404, f"msisdn {msisdn} not found")
    return SimResponse(
        reference="",
        msisdn=sim.msisdn,
        iccid=sim.iccid,
        plan_code=sim.plan_code,
        active=sim.active,
        roaming_enabled=sim.roaming_enabled,
    ).model_dump()


# ---- helpers ---


def _sim_response(msisdn: str, ref: str) -> dict:
    sim = ledger.get_sim(msisdn)
    assert sim is not None
    return SimResponse(
        reference=ref,
        msisdn=sim.msisdn,
        iccid=sim.iccid,
        plan_code=sim.plan_code,
        active=sim.active,
        roaming_enabled=sim.roaming_enabled,
    ).model_dump()
