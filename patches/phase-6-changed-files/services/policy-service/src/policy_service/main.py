"""policy-service entrypoint (CDC section 4.6): the mandatory, audited verdict checkpoint."""
from __future__ import annotations

from fastapi import FastAPI

from policy_service.audit import get_ledger
from policy_service.config import get_thresholds
from policy_service.schemas import EvaluateResponseRequest, PolicyContext, VerdictResponse
from policy_service.service import PolicyService

app = FastAPI(title="policy-service")
_service = PolicyService(get_ledger(), get_thresholds())


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/evaluate-action", response_model=VerdictResponse)
async def evaluate_action(ctx: PolicyContext) -> VerdictResponse:
    """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification for an action (audited)."""
    result = _service.evaluate_action(ctx)
    return VerdictResponse(verdict=result.verdict, rule_id=result.rule_id, justification=result.justification)


@app.post("/evaluate-response", response_model=VerdictResponse)
async def evaluate_response(req: EvaluateResponseRequest) -> VerdictResponse:
    """Guardrail an outbound response (audited)."""
    result = _service.evaluate_response(req.session_id, req.text)
    return VerdictResponse(verdict=result.verdict, rule_id=result.rule_id, justification=result.justification)


@app.get("/audit/verify")
async def audit_verify() -> dict:
    """Audit-chain integrity check (Blueprint section 12.3)."""
    return {"intact": get_ledger().verify(), "entries": len(get_ledger().entries)}