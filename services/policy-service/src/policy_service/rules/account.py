"""Account-action rules (CDC 5.6-5.8): recharge denominations, plan eligibility, roaming.

Deterministic counterpart to the top_up docstring: the catalog is enforced here, by the engine,
not by persuading the model. Thresholds come from config (twelve-factor), never hardcoded.
"""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_top_up(ctx, thresholds) -> VerdictResult | None:
    """Judge a TOP_UP action; None if not a top-up."""
    if ctx.action_type != "TOP_UP":
        return None
    if ctx.amount is None:
        return VerdictResult(REFUSED, "TOP_NO_AMOUNT", "recharge amount is missing")
    if ctx.amount <= 0:
        return VerdictResult(REFUSED, "TOP_INVALID_AMOUNT", "recharge amount must be positive")
    allowed = thresholds.topup_denominations
    if not _matches_denomination(ctx.amount, allowed):
        return VerdictResult(
            REFUSED,
            "TOP_DENOMINATION",
            "recharge amount is not a catalog denomination "
            f"({', '.join(f'{d:g}' for d in allowed)} TND)",
        )
    return VerdictResult(AUTHORIZED, "TOP_OK", "recharge within catalog")


def check_change_plan(ctx, thresholds) -> VerdictResult | None:
    """Judge a CHANGE_PLAN action; None if not a plan change."""
    if ctx.action_type != "CHANGE_PLAN":
        return None
    plan_code = (ctx.plan_code or "").strip()
    if not plan_code:
        return VerdictResult(REFUSED, "PLAN_NO_CODE", "target plan code is missing")
    allowed = thresholds.plan_codes
    if not allowed:
        return VerdictResult(
            ESCALATE, "PLAN_CATALOG_UNAVAILABLE", "plan catalog is not configured; needs review"
        )
    if plan_code.upper() not in allowed:
        return VerdictResult(REFUSED, "PLAN_UNKNOWN", f"plan '{plan_code}' is not in the catalog")
    return VerdictResult(AUTHORIZED, "PLAN_OK", "plan change within catalog")


def check_roaming(ctx, thresholds) -> VerdictResult | None:
    """Judge an ACTIVATE_ROAMING action; None if not a roaming change."""
    if ctx.action_type != "ACTIVATE_ROAMING":
        return None
    if ctx.enable is None:
        return VerdictResult(REFUSED, "ROAM_NO_DIRECTION", "roaming request has no on/off value")
    return VerdictResult(AUTHORIZED, "ROAM_OK", "roaming toggle within policy")


def _matches_denomination(amount: float, allowed: tuple[float, ...]) -> bool:
    """True when ``amount`` equals a catalog denomination within millime tolerance."""
    return any(abs(amount - d) < 0.0005 for d in allowed)
