"""execution-service entrypoint (CDC section 4.7): idempotent dispatch of authorized actions."""
from __future__ import annotations

from fastapi import FastAPI

from execution_service.audit import get_ledger
from execution_service.idempotency import InMemoryIdempotencyStore
from execution_service.schemas import ExecuteRequest, ExecuteResponse
from execution_service.service import ExecutionService

app = FastAPI(title="execution-service")
_service = ExecutionService(InMemoryIdempotencyStore(), get_ledger())


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    """Dispatch an AUTHORIZED action idempotently and audit the result."""
    return _service.execute(req)


@app.get("/audit/verify")
async def audit_verify() -> dict:
    """Audit-chain integrity check (Blueprint section 12.3)."""
    return {"intact": get_ledger().verify(), "entries": len(get_ledger().entries)}