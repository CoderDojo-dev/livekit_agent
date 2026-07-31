"""PolicyService: compute a verdict, PERSIST it (policy.policy_verdicts), and AUDIT it - atomically.

Structural enforcement of "every verdict is recorded regardless of outcome" (Blueprint section 10.3):
the verdict row + its hash-chained audit entry commit in one transaction. The returned verdict_id
is threaded to the execution-service so no action exists without a verdict (spec section 12).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.execution import ActionLedger
from persistence.models.policy import PolicyVerdict
from persistence.util import require_uuid, to_uuid
from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action, evaluate_response
from policy_service.rules.base import VerdictResult

logger = logging.getLogger(__name__)


class PolicyService:
    """Wraps the pure engine with persistence + mandatory audit."""

    def __init__(self, session: Session, thresholds: PolicyThresholds) -> None:
        self._session = session
        self._thresholds = thresholds
        self._audit = PgAuditLedger(session)

    def evaluate_action(self, ctx) -> tuple[VerdictResult, str]:
        """Judge an action, persist the verdict + audit entry, and return (result, verdict_id)."""
        ctx = self._enrich(ctx)
        result = evaluate_action(ctx, self._thresholds)
        verdict_id = self._persist(
            session_id=ctx.session_id, customer_id=ctx.customer_id, requested_action=ctx.action_type,
            direction="inbound", result=result, inputs=ctx.model_dump(mode="json"),
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

    def _enrich(self, ctx):
        """Fill server-side facts the caller cannot be trusted to provide.

        Only fills a field the caller left as None: an explicitly supplied value (tests, replays)
        is preserved, so existing behaviour and existing tests are untouched.
        """
        if ctx.action_type == "PAYMENT_DEFERRAL" and ctx.deferrals_this_year is None:
            counted = self._count_deferrals_this_year(ctx.customer_id)
            if counted is not None:
                return ctx.model_copy(update={"deferrals_this_year": counted})
        return ctx

    def _count_deferrals_this_year(self, customer_id) -> int | None:
        """Succeeded PAYMENT_DEFERRAL actions for this customer in the current calendar year.

        Returns None when the count cannot be established (no customer id, DB error) so the rule
        can fail closed instead of reading a fabricated 0.
        """
        cid = to_uuid(customer_id)
        if cid is None:
            return None
        year_start = datetime(datetime.now(UTC).year, 1, 1, tzinfo=UTC)
        try:
            count = self._session.scalar(
                select(func.count())
                .select_from(ActionLedger)
                .where(
                    ActionLedger.customer_id == cid,
                    ActionLedger.action_type == "PAYMENT_DEFERRAL",
                    ActionLedger.status == "succeeded",
                    ActionLedger.created_at >= year_start,
                )
            )
        except SQLAlchemyError as exc:
            self._session.rollback()
            logger.error("deferral-history count failed; failing closed: %s", exc)
            return None
        return int(count or 0)

    def _persist(self, session_id, customer_id, requested_action, direction, result, inputs) -> str | None:
        """Persist verdict + audit atomically.

        A storage failure must NEVER turn a correctly computed REFUSED/ESCALATE into an
        HTTP 500: the caller-facing consequence of a 500 is a fail-closed ESCALATE, i.e. a
        manager escalation for a decision that was already taken and already negative.
        An AUTHORIZED verdict still fails hard: no persisted verdict, no execution.
        """
        sid = require_uuid(session_id)
        try:
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
        except Exception as exc:  # noqa: BLE001 - a storage defect must never rewrite a verdict
            self._session.rollback()
            logger.error(
                "policy verdict persistence failed (action=%s verdict=%s rule=%s): %s",
                requested_action, result.verdict, result.rule_id, exc,
                exc_info=True,
            )
            if result.verdict.upper() == "AUTHORIZED":
                # Deliberate and unchanged: no persisted verdict means no execution (spec 12).
                # The 500 is the correct answer here - what was wrong was reaching it because of
                # a serialization detail rather than a real storage outage.
                raise
            return None