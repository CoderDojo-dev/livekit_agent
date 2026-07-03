"""execution-service entrypoint (CDC section 4.7): idempotent dispatch of authorized actions (Postgres)."""
from __future__ import annotations

from execution_service.schemas import ExecuteRequest, ExecuteResponse
from execution_service.service import ExecutionService
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence import get_session
from service_auth import require_internal_key

app = FastAPI(title="execution-service", dependencies=[Depends(require_internal_key)])


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest, session: Session = Depends(get_session)) -> ExecuteResponse:
    """Dispatch an AUTHORIZED action idempotently and audit the result."""
    return ExecutionService(session).execute(req)


@app.get("/audit/verify")
def audit_verify(session: Session = Depends(get_session)) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


def run() -> None:
    """Console-script entrypoint: `execution-service` (see [project.scripts]). Serves on :8105."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8105)
