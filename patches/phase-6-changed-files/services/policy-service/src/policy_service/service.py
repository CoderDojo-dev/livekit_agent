"""PolicyService: computes a verdict AND writes it to the audit ledger — never one without the other.

This is the structural enforcement of "every verdict is audited regardless of outcome"
(Blueprint section 10.3 / line 168). The endpoints call only this class.
"""
from __future__ import annotations

from audit_trail import AuditLedger

from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action, evaluate_response
from policy_service.rules.base import VerdictResult


class PolicyService:
    """Wraps the pure engine with mandatory audit logging."""

    def __init__(self, ledger: AuditLedger, thresholds: PolicyThresholds) -> None:
        self._ledger = ledger
        self._thresholds = thresholds

    def evaluate_action(self, ctx) -> VerdictResult:
        """Judge an action and audit the verdict before returning it."""
        result = evaluate_action(ctx, self._thresholds)
        self._ledger.append(
            ctx.session_id,
            "policy_verdict",
            {
                "action_type": ctx.action_type,
                "verdict": result.verdict,
                "rule_id": result.rule_id,
                "justification": result.justification,
            },
        )
        return result

    def evaluate_response(self, session_id: str, text: str) -> VerdictResult:
        """Guardrail an outbound response and audit the verdict before returning it."""
        result = evaluate_response(text)
        self._ledger.append(
            session_id,
            "outbound_guardrail",
            {"verdict": result.verdict, "rule_id": result.rule_id, "justification": result.justification},
        )
        return result

    @property
    def ledger(self) -> AuditLedger:
        return self._ledger