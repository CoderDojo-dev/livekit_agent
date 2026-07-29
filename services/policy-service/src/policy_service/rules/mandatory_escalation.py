"""Mandatory-escalation chain (CDC section 10.1): evaluated FIRST, short-circuits on first match."""
from __future__ import annotations

from policy_service.rules.base import ESCALATE, VerdictResult

IDENTITY_MAX_ATTEMPTS = 3
CLARIFICATION_MAX_ATTEMPTS = 2


def check_mandatory(ctx) -> VerdictResult | None:
    """Return an ESCALATE verdict if any mandatory trigger fires, else None."""
    if ctx.fraud_suspected:
        return VerdictResult(ESCALATE, "ESC_FRAUD", "fraud suspicion on the account")
    # is_vip is deliberately NOT escalated here (P9). VIP customers must pass through
    # business rules like everyone else. The field remains in PolicyContext for audit.
    if ctx.frustration:
        return VerdictResult(ESCALATE, "ESC_FRUSTRATION", "confirmed caller frustration")
    if ctx.clarification_attempts >= CLARIFICATION_MAX_ATTEMPTS:
        return VerdictResult(ESCALATE, "ESC_CLARIFICATION", "two failed clarification attempts")
    if ctx.identity_attempts >= IDENTITY_MAX_ATTEMPTS and not ctx.identity_verified:
        return VerdictResult(ESCALATE, "ESC_IDENTITY_FAILURE", "repeated identity-verification failure")
    return None