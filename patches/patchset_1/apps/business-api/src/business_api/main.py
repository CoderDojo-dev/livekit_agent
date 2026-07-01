"""business-api entrypoint (spec section 17): read-or-audited supervisor/admin endpoints.

RBAC per the section 17 matrix (conseiller / superviseur / administrateur). No endpoint mutates
the audit ledger; the integrity job only verifies it.
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from persistence import get_session

app = FastAPI(title="business-api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Role"],
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: Session = Depends(get_session),
                 role: str = Depends(require_role("conseiller"))) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: Session = Depends(get_session),
                   role: str = Depends(require_role("conseiller"))) -> dict:
    """Masked transcript + sentiment timeline + disposition for a call session."""
    data = SupervisionRepository(session).session_detail(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.get("/api/v1/escalations")
def escalations(status: str = "open", session: Session = Depends(get_session),
                role: str = Depends(require_role("superviseur"))) -> dict:
    """Escalation queue with dossiers."""
    return {"escalations": SupervisionRepository(session).escalations(status)}


@app.get("/api/v1/policy/verdicts")
def verdicts(session_id: str, session: Session = Depends(get_session),
             role: str = Depends(require_role("superviseur"))) -> dict:
    """All policy verdicts for a session (audit review)."""
    return {"verdicts": SupervisionRepository(session).verdicts(session_id)}


@app.get("/api/v1/actions")
def actions(status: str = "failed", session: Session = Depends(get_session),
            role: str = Depends(require_role("superviseur"))) -> dict:
    """Failed / retrying actions from the action ledger."""
    return {"actions": SupervisionRepository(session).actions(status)}


@app.get("/api/v1/kpis")
def kpis(session: Session = Depends(get_session),
         role: str = Depends(require_role("superviseur"))) -> dict:
    """Containment / escalation KPIs over the persisted conversation record."""
    return SupervisionRepository(session).kpis().__dict__


@app.get("/api/v1/audit/verify")
def audit_verify(from_seq: int | None = None, to_seq: int | None = None,
                 session: Session = Depends(get_session),
                 role: str = Depends(require_role("administrateur"))) -> dict:
    """Run the hash-chain integrity check (whole chain; range is a later refinement)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


@app.get("/api/v1/reference/business-rules")
def business_rules(session: Session = Depends(get_session),
                   role: str = Depends(require_role("administrateur"))) -> dict:
    """List the versioned Policy rule registry."""
    return {"rules": SupervisionRepository(session).business_rules()}


@app.get("/api/v1/jobs/integrity")
def integrity(session: Session = Depends(get_session),
              role: str = Depends(require_role("administrateur"))) -> dict:
    """Cross-domain referential integrity + audit-chain verification (spec section 20.4)."""
    report = run_integrity(session)
    return {
        "ok": report.ok, "orphans": report.orphans,
        "audit_chain_intact": report.audit_chain_intact, "audit_entries": report.audit_entries,
    }


@app.post("/api/v1/jobs/retention")
def retention(retention_days: int = 90, dry_run: bool = True,
              session: Session = Depends(get_session),
              role: str = Depends(require_role("administrateur"))) -> dict:
    """Run the audited retention/purge job (dry_run=True by default) - spec section 8.3."""
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__
