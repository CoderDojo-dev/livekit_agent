"""execution-service entrypoint (CDC section 4.7): idempotent dispatch of authorized actions (Postgres)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from execution_service.schemas import ExecuteRequest, ExecuteResponse
from execution_service.service import ExecutionService
from persistence import get_session
from service_auth import require_internal_key
from observability_kit import configure_tracer, trace_requests

app = FastAPI(title="execution-service", dependencies=[Depends(require_internal_key)])
configure_tracer("execution-service")
trace_requests(app, "execution-service")
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest, session: DbSession) -> ExecuteResponse:
    """Dispatch an AUTHORIZED action idempotently and audit the result."""
    try:
        return ExecutionService(session).execute(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/audit/verify")
def audit_verify(session: DbSession) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


def run() -> None:
    """Console-script entrypoint: `execution-service` (see [project.scripts]). Serves on :8105."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8105)
