"""ExecutionService: idempotent dispatch + execution-result audit.

Order: check idempotency (replay if seen) -> dispatch -> store -> audit the result. A duplicate
key never double-executes; every execution is recorded (Blueprint section 9.3 / line 365).
"""
from __future__ import annotations

from audit_trail import AuditLedger

from execution_service.executor import dispatch
from execution_service.idempotency import InMemoryIdempotencyStore
from execution_service.schemas import ExecuteRequest, ExecuteResponse


class ExecutionService:
    """Dispatches AUTHORIZED actions exactly once per idempotency key, with an audit trail."""

    def __init__(self, store: InMemoryIdempotencyStore, ledger: AuditLedger) -> None:
        self._store = store
        self._ledger = ledger

    def execute(self, req: ExecuteRequest) -> ExecuteResponse:
        """Dispatch ``req`` once; a repeat key returns the original reference with replay=True."""
        cached = self._store.get(req.idempotency_key)
        if cached is not None:
            return ExecuteResponse(**{**cached, "replay": True})

        reference = dispatch(req.action_type, req.payload)
        response = {
            "status": "executed",
            "reference": reference,
            "action_type": req.action_type,
            "replay": False,
        }
        self._store.put(req.idempotency_key, response)
        self._ledger.append(
            req.session_id,
            "execution_result",
            {
                "action_type": req.action_type,
                "reference": reference,
                "idempotency_key": req.idempotency_key,
            },
        )
        return ExecuteResponse(**response)

    @property
    def ledger(self) -> AuditLedger:
        return self._ledger