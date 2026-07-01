"""policy-service entrypoint (CDC section 4.6): the mandatory, audited verdict checkpoint (Postgres)."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence import get_session
from policy_service.config import get_thresholds
from policy_service.schemas import EvaluateResponseRequest, PolicyContext, VerdictResponse
from policy_service.service import PolicyService

app = FastAPI(title="policy-service")


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/evaluate-action", response_model=VerdictResponse)
def evaluate_action(ctx: PolicyContext, session: Session = Depends(get_session)) -> VerdictResponse:
    """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification + verdict_id (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_action(ctx)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.post("/evaluate-response", response_model=VerdictResponse)
def evaluate_response(
    req: EvaluateResponseRequest, session: Session = Depends(get_session)
) -> VerdictResponse:
    """Guardrail an outbound response (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_response(req.session_id, req.text)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.get("/audit/verify")
def audit_verify(session: Session = Depends(get_session)) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}