"""Payment-deferral rule (CDC section 6.2): min account age, yearly cap, unpaid-amount review."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_deferral(ctx, thresholds) -> VerdictResult | None:
    """Judge a PAYMENT_DEFERRAL action; None if not a deferral."""
    if ctx.action_type != "PAYMENT_DEFERRAL":
        return None
    if ctx.account_age_days < thresholds.deferral_min_age_days:
        return VerdictResult(
            REFUSED,
            "DEF_MIN_AGE",
            f"account age {ctx.account_age_days}d below minimum {thresholds.deferral_min_age_days}d",
        )
    if ctx.deferrals_this_year >= thresholds.deferral_max_per_year:
        return VerdictResult(REFUSED, "DEF_CAP", "yearly payment-deferral cap reached")
    if ctx.unpaid_amount > thresholds.deferral_unpaid_threshold:
        return VerdictResult(
            ESCALATE,
            "DEF_UNPAID_REVIEW",
            f"unpaid {ctx.unpaid_amount:.3f} above {thresholds.deferral_unpaid_threshold:.3f} TND; needs review",
        )
    return VerdictResult(AUTHORIZED, "DEF_OK", "deferral within policy")