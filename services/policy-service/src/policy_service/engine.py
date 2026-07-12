"""The deterministic engine (the safety core). Pure functions — no I/O, fully unit-testable.

Order (Blueprint section 10): mandatory-escalation chain first (short-circuit), then a
defense-in-depth identity backstop for sensitive actions, then the action-specific business
rules. Default is AUTHORIZED only if no rule objects.
"""
from __future__ import annotations

from datetime import UTC, datetime

from policy_service.rules.base import AUTHORIZED, ESCALATE, VerdictResult
from policy_service.rules.deferral import check_deferral
from policy_service.rules.mandatory_escalation import check_mandatory
from policy_service.rules.outbound import check_outbound
from policy_service.rules.payment import check_payment
from policy_service.rules.sim import check_sim

SENSITIVE_ACTIONS = frozenset(
    {
        "EXECUTE_PAYMENT",
        "PAYMENT_DEFERRAL",
        "UNBLOCK_SIM",
        "REPLACE_SIM",
        "REACTIVATE_SIM",
        "TOP_UP",
        "CHANGE_PLAN",
        "ACTIVATE_ROAMING",
    }
)

# Explicit allowlist. Anything not listed here is unknown and must never execute.
SUPPORTED_ACTIONS = SENSITIVE_ACTIONS

_ACTION_RULES = (check_payment, check_deferral, check_sim)


def evaluate_action(ctx, thresholds) -> VerdictResult:
    """Return the binding three-way verdict for an action (never raises)."""
    if ctx.action_type not in SUPPORTED_ACTIONS:
        return VerdictResult(
            ESCALATE,
            "POLICY_UNKNOWN_ACTION",
            f"action '{ctx.action_type}' is not explicitly supported by policy",
        )

    mandatory = check_mandatory(ctx)
    if mandatory is not None:
        return mandatory

    if ctx.action_type in SENSITIVE_ACTIONS:
        if not ctx.identity_verified:
            return VerdictResult(
                ESCALATE,
                "IDENTITY_STEP_UP",
                "sensitive action requires verified identity",
            )
        if not ctx.customer_id or ctx.verified_customer_id != ctx.customer_id:
            return VerdictResult(
                ESCALATE,
                "IDENTITY_CUSTOMER_MISMATCH",
                "verification is not bound to the action customer",
            )
        if (
            ctx.identity_expires_at is None
            or ctx.identity_expires_at <= datetime.now(UTC)
        ):
            return VerdictResult(
                ESCALATE,
                "IDENTITY_EXPIRED",
                "identity verification is no longer fresh",
            )

    for rule in _ACTION_RULES:
        result = rule(ctx, thresholds)
        if result is not None:
            return result

    # Known account actions currently share the mandatory identity checks above.
    # This is explicit authorization, not an open-ended default allow.
    return VerdictResult(
        AUTHORIZED,
        "KNOWN_ACTION_AUTHORIZED",
        "known action passed mandatory identity and escalation checks",
    )


def evaluate_response(text: str) -> VerdictResult:
    """Return the outbound guardrail verdict for a response string."""
    return check_outbound(text)