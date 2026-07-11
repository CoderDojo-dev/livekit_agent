"""Account-services tools (CDC 5.6-5.8): plan details, plan change, recharge, roaming.

Plan-details is a read from the pre-fetched context. The three state changes are identity-gated
first, then flow through the one guarded path (Decision -> Policy -> Execution), so they are
verdict-checked, idempotent and audited like every other sensitive action.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from tools import outcomes
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified


@function_tool()
async def get_plan_details(context: RunContext) -> dict:
    """Return verified personal account and plan information."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate(
            "IDENTITY_REQUIRED",
            "Identity verification is required.",
        )

    customer = context.session.userdata.customer_context
    if customer is None:
        return outcomes.escalate(
            "UNKNOWN_CALLER",
            "No customer context is available.",
        )

    masked_msisdn = f"******{customer.msisdn[-4:]}"
    return {
        "outcome": "success",
        "full_name": customer.full_name,
        "masked_msisdn": masked_msisdn,
        "subscription_type": customer.subscription_type,
        "message": (
            f"The account belongs to {customer.full_name}. "
            f"The line ending in {customer.msisdn[-4:]} uses "
            f"{customer.subscription_type}."
        ),
    }

@function_tool()
async def change_plan(context: RunContext, new_plan_code: str) -> dict:
    """Change the caller's plan to ``new_plan_code``. Identity-gated + verdict-checked."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "CHANGE_PLAN", {"plan_code": new_plan_code})


@function_tool()
async def top_up(context: RunContext, amount: float) -> dict:
    """Top up the caller's prepaid balance by ``amount`` TND. Identity-gated + verdict-checked."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "TOP_UP", {"amount": amount})


@function_tool()
async def toggle_roaming(context: RunContext, enable: bool) -> dict:
    """Enable or disable roaming for the caller's line. Identity-gated + verdict-checked."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "ACTIVATE_ROAMING", {"enable": enable})
