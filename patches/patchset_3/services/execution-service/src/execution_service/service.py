"""ExecutionService: idempotent action ledger (Postgres) + execution-result audit.

execute(): look up the idempotency key (replay if seen) -> INSERT a pending action_ledger row
(UNIQUE key enforces at-most-once even under a race) -> dispatch -> mark succeeded -> audit, all
in one transaction. Every row carries the policy_verdict_id that authorized it (spec section 12).
"""
from __future__ import annotations

import logging

from audit_trail import PgAuditLedger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from execution_service.executor import dispatch, target_domain
from execution_service.projections import project_domain_effect
from execution_service.schemas import ExecuteRequest, ExecuteResponse
from persistence.models.execution import ActionLedger
from persistence.util import require_uuid, to_uuid

logger = logging.getLogger(__name__)


class ExecutionService:
    """Dispatches AUTHORIZED actions exactly once per idempotency key, with an audit trail."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = PgAuditLedger(session)

    def execute(self, req: ExecuteRequest) -> ExecuteResponse:
        """Dispatch ``req`` once; a repeat key returns the original reference with replay=True."""
        existing = self._by_key(req.idempotency_key)
        if existing is not None:
            return self._replay(existing)

        row = ActionLedger(
            session_id=require_uuid(req.session_id),
            customer_id=to_uuid(req.customer_id),
            subscription_id=to_uuid(req.subscription_id),
            action_type=req.action_type,
            target_domain=req.target_domain or target_domain(req.action_type),
            idempotency_key=req.idempotency_key,
            policy_verdict_id=require_uuid(req.policy_verdict_id),
            parameters=req.payload,
            status="pending",
            attempt_count=1,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            existing = self._by_key(req.idempotency_key)
            if existing is not None:  # lost a race on the same key -> replay
                return self._replay(existing)
            raise  # a different constraint (e.g. unknown policy_verdict_id) - surface it

        reference = dispatch(req.action_type, req.payload, customer_id=req.customer_id, idempotency_key=req.idempotency_key)
        row.status = "succeeded"
        row.adapter_reference = reference
        self._audit.append(
            require_uuid(req.session_id), "execution_result",
            {"action_type": req.action_type, "reference": reference, "idempotency_key": req.idempotency_key},
            entity_reference=f"action_ledger:{row.id}",
        )

        # Project the domain effect (payment / plan / recharge / sim case) in a SAVEPOINT, so a
        # projection failure can never undo the action ledger or the audit chain.
        try:
            with self._session.begin_nested():
                project_domain_effect(self._session, req, row)
        except Exception as exc:  # noqa: BLE001
            logger.warning("domain projection failed (%s): %s", req.action_type, exc)

        self._session.commit()
        return ExecuteResponse(status="executed", reference=reference, action_type=req.action_type, replay=False)

    def _by_key(self, key: str) -> ActionLedger | None:
        return self._session.scalar(select(ActionLedger).where(ActionLedger.idempotency_key == key))

    @staticmethod
    def _replay(row: ActionLedger) -> ExecuteResponse:
        return ExecuteResponse(
            status="executed", reference=row.adapter_reference or "", action_type=row.action_type, replay=True
        )