"""policy-service entrypoint (CDC section 4.6): the mandatory, audited verdict checkpoint (Postgres)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from observability_kit import configure_tracer, trace_requests
from persistence import get_session
from policy_service.config import get_thresholds
from policy_service.schemas import EvaluateResponseRequest, PolicyContext, VerdictResponse
from policy_service.service import PolicyService
from service_auth import require_internal_key

app = FastAPI(title="policy-service", dependencies=[Depends(require_internal_key)])
configure_tracer("policy-service")
trace_requests(app, "policy-service")
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/evaluate-action", response_model=VerdictResponse)
def evaluate_action(ctx: PolicyContext, session: DbSession) -> VerdictResponse:
    """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification + verdict_id (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_action(ctx)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.post("/evaluate-response", response_model=VerdictResponse)
def evaluate_response(
    req: EvaluateResponseRequest, session: DbSession
) -> VerdictResponse:
    """Guardrail an outbound response (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_response(req.session_id, req.text)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.get("/audit/verify")
def audit_verify(session: DbSession) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


def run() -> None:
    """Console-script entrypoint: `policy-service` (see [project.scripts]). Serves on :8104."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8104)
