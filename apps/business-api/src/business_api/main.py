"""business-api entrypoint (spec section 17): read-or-audited supervisor/admin endpoints.

RBAC per the section 17 matrix (conseiller / superviseur / administrateur). No endpoint mutates
the audit ledger; the integrity job only verifies it.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from business_api import advisors as advisor_repo
from business_api import callbacks as callback_repo
from business_api import policy_view
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from pydantic import BaseModel
from persistence import get_session

app = FastAPI(title="business-api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Role"],
)

DbSession = Annotated[Session, Depends(get_session)]
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Masked transcript + sentiment timeline + disposition for a call session."""
    data = SupervisionRepository(session).session_detail(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.get("/api/v1/escalations")
def escalations(session: DbSession, role: SuperviseurRole, status: str = "open") -> dict:
    """Escalation queue with dossiers."""
    return {"escalations": SupervisionRepository(session).escalations(status)}


@app.get("/api/v1/policy/verdicts")
def verdicts(session_id: str, session: DbSession, role: SuperviseurRole) -> dict:
    """All policy verdicts for a session (audit review)."""
    return {"verdicts": SupervisionRepository(session).verdicts(session_id)}


@app.get("/api/v1/actions")
def actions(session: DbSession, role: SuperviseurRole, status: str = "failed") -> dict:
    """Failed / retrying actions from the action ledger."""
    return {"actions": SupervisionRepository(session).actions(status)}


@app.get("/api/v1/kpis")
def kpis(session: DbSession, role: SuperviseurRole) -> dict:
    """Containment / escalation KPIs over the persisted conversation record."""
    return SupervisionRepository(session).kpis().__dict__


@app.get("/api/v1/system/overview")
def system_overview(session: DbSession, role: SuperviseurRole) -> dict:
    """Real-time system overview: database counts + service status matrix."""
    return SupervisionRepository(session).system_overview()


@app.get("/api/v1/telemetry/timeline")
def telemetry_timeline(session: DbSession, role: SuperviseurRole) -> dict:
    """Time-series metrics and verdict distributions derived from persisted records."""
    return SupervisionRepository(session).telemetry_timeline()


@app.get("/api/v1/audit/verify")
def audit_verify(
    session: DbSession,
    role: AdministrateurRole,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> dict:
    """Run the hash-chain integrity check (whole chain; range is a later refinement)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


@app.get("/api/v1/reference/business-rules")
def business_rules(session: DbSession, role: AdministrateurRole) -> dict:
    """List the versioned Policy rule registry with the LIVE enforced thresholds.

    The DB row supplies governance metadata; the numeric thresholds are overlaid from the same
    POLICY_* env the policy engine enforces, so the registry can never drift from what is applied.
    """
    rows = SupervisionRepository(session).business_rules()
    return {"rules": policy_view.overlay(rows)}


@app.get("/api/v1/jobs/integrity")
def integrity(session: DbSession, role: AdministrateurRole) -> dict:
    """Cross-domain referential integrity + audit-chain verification (spec section 20.4)."""
    report = run_integrity(session)
    return {
        "ok": report.ok, "orphans": report.orphans,
        "audit_chain_intact": report.audit_chain_intact, "audit_entries": report.audit_entries,
    }


@app.post("/api/v1/jobs/retention")
def retention(
    session: DbSession,
    role: AdministrateurRole,
    retention_days: int = 90,
    dry_run: bool = True,
) -> dict:
    """Run the audited retention/purge job (dry_run=True by default) - spec section 8.3."""
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__


# ---------------- Advisor registry (admin dashboard + agent routing) ----------------
class AdvisorPayload(BaseModel):
    """Advisor create/update body. Skills are tags matched against the escalating persona."""

    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    sip_uri: str | None = None
    skills: list[str] | None = None
    language: str | None = None
    status: str | None = None
    max_concurrent_calls: int | None = None
    is_on_call: bool | None = None
    is_active: bool | None = None


@app.get("/api/v1/advisors")
def list_advisors(session: DbSession, role: SuperviseurRole, include_inactive: bool = False) -> dict:
    """List advisors (admin dashboard)."""
    return {"advisors": advisor_repo.list_advisors(session, include_inactive)}


@app.post("/api/v1/advisors", status_code=201)
def create_advisor(payload: AdvisorPayload, session: DbSession, role: AdministrateurRole) -> dict:
    """Register a new advisor."""
    if not payload.full_name:
        raise HTTPException(status_code=400, detail="full_name is required")
    try:
        result = advisor_repo.create_advisor(session, payload.model_dump(exclude_none=True))
        session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/v1/advisors/{advisor_id}")
def update_advisor(advisor_id: str, payload: AdvisorPayload, session: DbSession,
                   role: AdministrateurRole) -> dict:
    """Update an advisor (availability, skills, contact details)."""
    try:
        updated = advisor_repo.update_advisor(session, advisor_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return updated


@app.delete("/api/v1/advisors/{advisor_id}")
def delete_advisor(advisor_id: str, session: DbSession, role: AdministrateurRole) -> dict:
    """Remove an advisor from the registry."""
    if not advisor_repo.delete_advisor(session, advisor_id):
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return {"deleted": True, "advisor_id": advisor_id}


@app.post("/api/v1/advisors/claim")
def claim_advisor(session: DbSession, role: ConseillerRole, skill_tag: str = "general") -> dict:
    """Atomically reserve an available advisor for ``skill_tag`` (used by the voice agent).

    Returns {"advisor": null} when nobody is free - the caller then offers a callback. It never
    invents a destination.
    """
    claimed = advisor_repo.claim_advisor(session, skill_tag)
    session.commit()
    return {"advisor": claimed}


@app.post("/api/v1/advisors/{advisor_id}/release")
def release_advisor(advisor_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Release a claimed advisor (call ended, or the transfer failed)."""
    if not advisor_repo.release_advisor(session, advisor_id):
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return {"released": True, "advisor_id": advisor_id}


@app.get("/api/v1/advisors/on-call")
def on_call_advisors(session: DbSession, role: ConseillerRole) -> dict:
    """Advisors who receive the dossier when a callback is scheduled."""
    return {"advisors": advisor_repo.on_call_advisors(session)}


# ---------------- Callback queue (the promise made when no advisor was free) ----------------
class CallbackOutcome(BaseModel):
    """Result of an attempted callback."""

    note: str = ""
    reached: bool = True      # False -> the caller did not answer; return it to the queue
    advisor_id: str | None = None


@app.get("/api/v1/callbacks")
def list_callbacks(session: DbSession, role: ConseillerRole, status: str = "pending",
                   overdue_only: bool = False, limit: int = 100) -> dict:
    """The callback queue, soonest and highest priority first."""
    return {"callbacks": callback_repo.list_callbacks(session, status, overdue_only, limit)}


@app.get("/api/v1/callbacks/stats")
def callback_stats(session: DbSession, role: SuperviseurRole) -> dict:
    """Queue health: pending, overdue, completed."""
    return callback_repo.queue_stats(session)


@app.post("/api/v1/callbacks/claim")
def claim_callback(session: DbSession, role: ConseillerRole, advisor_id: str | None = None) -> dict:
    """Atomically take the next due callback. {"callback": null} when the queue is empty."""
    claimed = callback_repo.claim_next(session, advisor_id)
    session.commit()
    return {"callback": claimed}


@app.post("/api/v1/callbacks/{callback_id}/complete")
def complete_callback(callback_id: str, outcome: CallbackOutcome, session: DbSession,
                      role: ConseillerRole) -> dict:
    """Close a callback with its outcome, or return it to the queue if the caller did not answer."""
    updated = callback_repo.complete_callback(session, callback_id, outcome.note, outcome.reached)
    if updated is None:
        raise HTTPException(status_code=404, detail="callback not found")
    session.commit()
    return updated


@app.post("/api/v1/callbacks/{callback_id}/cancel")
def cancel_callback(callback_id: str, outcome: CallbackOutcome, session: DbSession,
                    role: SuperviseurRole) -> dict:
    """Cancel a callback that is no longer needed."""
    updated = callback_repo.cancel_callback(session, callback_id, outcome.note)
    if updated is None:
        raise HTTPException(status_code=404, detail="callback not found")
    session.commit()
    return updated


def run() -> None:
    """Console-script entrypoint: `business-api` (see [project.scripts]). Serves on :8108."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8108)
