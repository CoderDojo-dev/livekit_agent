"""PolicyService: compute a verdict, PERSIST it (policy.policy_verdicts), and AUDIT it - atomically.

Structural enforcement of "every verdict is recorded regardless of outcome" (Blueprint section 10.3):
the verdict row + its hash-chained audit entry commit in one transaction. The returned verdict_id
is threaded to the execution-service so no action exists without a verdict (spec section 12).
"""
from __future__ import annotations

from audit_trail import PgAuditLedger
from sqlalchemy.orm import Session

from persistence.models.policy import PolicyVerdict
from persistence.util import require_uuid, to_uuid
from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action, evaluate_response
from policy_service.rules.base import VerdictResult


class PolicyService:
    """Wraps the pure engine with persistence + mandatory audit."""

    def __init__(self, session: Session, thresholds: PolicyThresholds) -> None:
        self._session = session
        self._thresholds = thresholds
        self._audit = PgAuditLedger(session)

    def evaluate_action(self, ctx) -> tuple[VerdictResult, str]:
        """Judge an action, persist the verdict + audit entry, and return (result, verdict_id)."""
        result = evaluate_action(ctx, self._thresholds)
        verdict_id = self._persist(
            session_id=ctx.session_id, customer_id=ctx.customer_id, requested_action=ctx.action_type,
            direction="inbound", result=result, inputs=ctx.model_dump(),
        )
        return result, verdict_id

    def evaluate_response(self, session_id: str, text: str) -> tuple[VerdictResult, str]:
        """Guardrail an outbound response, persist + audit, return (result, verdict_id)."""
        result = evaluate_response(text)
        verdict_id = self._persist(
            session_id=session_id, customer_id=None, requested_action="outbound_response",
            direction="outbound", result=result, inputs={"length": len(text)},
        )
        return result, verdict_id

    def _persist(self, session_id, customer_id, requested_action, direction, result, inputs) -> str:
        sid = require_uuid(session_id)
        verdict = PolicyVerdict(
            session_id=sid,
            customer_id=to_uuid(customer_id),
            requested_action=requested_action,
            direction=direction,
            verdict=result.verdict.upper(),
            rule_id=result.rule_id,
            justification=result.justification,
            inputs_snapshot=inputs,
        )
        self._session.add(verdict)
        self._session.flush()
        self._audit.append(
            sid, "policy_verdict",
            {"action": requested_action, "verdict": result.verdict, "rule_id": result.rule_id},
            entity_reference=f"policy_verdicts:{verdict.id}",
        )
        self._session.commit()
        return str(verdict.id)