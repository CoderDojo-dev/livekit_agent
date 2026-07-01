"""SIM rule (CDC section 6.3): every SIM operation requires prior identity verification."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, VerdictResult

SIM_ACTIONS = frozenset({"UNBLOCK_SIM", "REPLACE_SIM", "REACTIVATE_SIM"})


def check_sim(ctx, thresholds) -> VerdictResult | None:
    """Judge a SIM action; None if not a SIM action."""
    if ctx.action_type not in SIM_ACTIONS:
        return None
    if not ctx.identity_verified:
        return VerdictResult(ESCALATE, "SIM_IDENTITY_REQUIRED", "SIM operation requires prior identity verification")
    return VerdictResult(AUTHORIZED, "SIM_OK", "SIM operation within policy")