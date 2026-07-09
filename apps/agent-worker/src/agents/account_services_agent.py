"""AccountServicesAgent (CDC 5.6-5.8): plan consultation/change, prepaid recharge, roaming.

Inherits BaseTelecomAgent so it gets the shared per-turn sentiment scoring + proactive
de-escalation + conversation logging, like every other persona. All state changes go through the
guarded action path.
"""
from __future__ import annotations

from tools.account_tools import change_plan, get_plan_details, toggle_roaming, top_up
from tools.escalation_tools import escalate_to_manager

from agents.base_agent import BaseTelecomAgent


class AccountServicesAgent(BaseTelecomAgent):
    """Lower-risk account-management persona; every state change is verdict-checked + audited."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle account services: plan consultation, plan changes, prepaid recharges, "
                "and roaming. For the current plan call get_plan_details. To change a plan use "
                "change_plan. For a recharge use top_up. For roaming use toggle_roaming. If the "
                "caller is upset or asks for a human, call escalate_to_manager. Keep replies short."
            ),
            chat_ctx=chat_ctx,
            tools=[get_plan_details, change_plan, top_up, toggle_roaming, escalate_to_manager],
        )

    async def on_enter(self) -> None:
        """Greet briefly and invite the account-management request."""
        await self.session.generate_reply(
            instructions="Briefly tell the caller you can help with plans, recharges and roaming."
        )