"""Payment rule (CDC section 6.1): verbal confirmation, amount sanity, automatic cap."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_payment(ctx, thresholds) -> VerdictResult | None:
    """Judge an EXECUTE_PAYMENT action; None if not a payment."""
    if ctx.action_type != "EXECUTE_PAYMENT":
        return None
    if not ctx.payment_confirmed:
        return VerdictResult(REFUSED, "PAY_NO_CONFIRMATION", "verbal confirmation required before payment")
    if ctx.amount is None:
        return VerdictResult(REFUSED, "PAY_NO_AMOUNT", "payment amount is missing")
    if ctx.amount <= 0:
        return VerdictResult(REFUSED, "PAY_INVALID_AMOUNT", "payment amount must be positive")
    if ctx.unpaid_amount > 0 and ctx.amount > ctx.unpaid_amount + 0.0005:
        return VerdictResult(
            ESCALATE,
            "PAY_ABOVE_DUE",
            f"amount {ctx.amount:.3f} exceeds the {ctx.unpaid_amount:.3f} TND currently due",
        )
    if ctx.amount > thresholds.payment_cap:
        return VerdictResult(
            ESCALATE,
            "PAY_ABOVE_CAP",
            f"amount {ctx.amount:.3f} above automatic cap {thresholds.payment_cap:.3f} TND",
        )
    return VerdictResult(AUTHORIZED, "PAY_OK", "payment within policy")