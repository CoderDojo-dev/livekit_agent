"""Offline tests: idempotent dispatch + execution-result audit (no network)."""
from __future__ import annotations

from audit_trail import AuditLedger

from execution_service.idempotency import InMemoryIdempotencyStore
from execution_service.schemas import ExecuteRequest
from execution_service.service import ExecutionService


def _service() -> ExecutionService:
    return ExecutionService(InMemoryIdempotencyStore(), AuditLedger())


def test_executes_and_returns_reference() -> None:
    service = _service()
    resp = service.execute(ExecuteRequest(idempotency_key="k1", action_type="PAYMENT_DEFERRAL"))
    assert resp.status == "executed"
    assert resp.reference.startswith("DEF-")
    assert resp.replay is False


def test_same_key_is_idempotent_and_does_not_re_execute() -> None:
    service = _service()
    first = service.execute(ExecuteRequest(idempotency_key="k2", action_type="EXECUTE_PAYMENT"))
    second = service.execute(ExecuteRequest(idempotency_key="k2", action_type="EXECUTE_PAYMENT"))
    assert second.reference == first.reference  # same reference, no second dispatch
    assert second.replay is True
    assert len(service.ledger.entries) == 1   # only the first execution was audited


def test_audit_chain_intact() -> None:
    service = _service()
    service.execute(ExecuteRequest(idempotency_key="a", action_type="UNBLOCK_SIM"))
    service.execute(ExecuteRequest(idempotency_key="b", action_type="EXECUTE_PAYMENT"))
    assert service.ledger.verify() is True
    assert len(service.ledger.entries) == 2