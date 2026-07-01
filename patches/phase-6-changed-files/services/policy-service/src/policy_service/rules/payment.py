"""Payment rule (CDC section 6.1): verbal confirmation + automatic-processing cap."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_payment(ctx, thresholds) -> VerdictResult | None:
    """Judge an EXECUTE_PAYMENT action; None if not a payment."""
    if ctx.action_type != "EXECUTE_PAYMENT":
        return None
    if not ctx.payment_confirmed:
        return VerdictResult(REFUSED, "PAY_NO_CONFIRMATION", "verbal confirmation required before payment")
    if ctx.amount is not None and ctx.amount > thresholds.payment_cap:
        return VerdictResult(
            ESCALATE,
            "PAY_ABOVE_CAP",
            f"amount {ctx.amount:.3f} above automatic cap {thresholds.payment_cap:.3f} TND",
        )
    return VerdictResult(AUTHORIZED, "PAY_OK", "payment within policy")