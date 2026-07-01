"""Account-services tools (CDC 5.6-5.8): plan details, plan change, recharge, roaming.

Plan-details is a read from the pre-fetched context; the three state changes flow through the one
guarded path (Decision -> Policy -> Execution), so they are verdict-checked, idempotent and audited
like every other sensitive action. Returns are plain strings the persona can speak.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from tools.guarded_action import execute_guarded_action


@function_tool()
async def get_plan_details(context: RunContext) -> str:
    """Tell the caller their current plan and line (read-only, from the pre-fetched profile)."""
    customer = context.session.userdata.customer_context
    if customer is None:
        return "I can't see an active line for this number yet."
    return f"You're on {customer.subscription_type} for the line {customer.msisdn}."


@function_tool()
async def change_plan(context: RunContext, new_plan_code: str) -> dict:
    """Change the caller's plan to ``new_plan_code`` (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "CHANGE_PLAN", {"plan_code": new_plan_code})


@function_tool()
async def top_up(context: RunContext, amount: float) -> dict:
    """Top up the caller's prepaid balance by ``amount`` TND (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "TOP_UP", {"amount": amount})


@function_tool()
async def toggle_roaming(context: RunContext, enable: bool) -> dict:
    """Enable or disable roaming for the caller's line (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "ACTIVATE_ROAMING", {"enable": enable})