"""BillingAgent: bill consultation (read), payment-deferral (guarded) (CDC 5.1-5.3).

Phase 6: request_payment_deferral now runs the full Decision -> Policy -> (audit) façade after
identity verification. Execution of an AUTHORIZED deferral lands in Phase 7.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from clients.context_client import get_context_client
from mcp_clients.knowledge_glpi_toolset import build_knowledge_toolset
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified


@function_tool()
async def request_payment_deferral(context: RunContext, requested_days: int) -> dict:
    """Request a payment deferral of the given number of days (CDC section 5.3).

    Identity-gated, then Decision -> Policy -> (audit). Returns a structured outcome:
    'authorized' (pending execution in Phase 7), 'refused', or 'escalate'.
    """
    if not await ensure_identity_verified(context):
        return {"outcome": "escalate", "reason": "identity_not_verified"}

    user_data = context.session.userdata
    unpaid_amount = 0.0
    if user_data.customer_context is not None:
        invoices = await get_context_client().get_invoices(user_data.customer_context.customer_id)
        unpaid_amount = sum(inv["amount"] for inv in invoices if inv.get("status") != "paid")

    return await execute_guarded_action(
        context,
        "PAYMENT_DEFERRAL",
        {"requested_days": requested_days, "unpaid_amount": unpaid_amount, "deferrals_this_year": 0},
    )


class BillingAgent(Agent):
    """Concentrates billing/payment risk. Reads are free; sensitive writes are guarded + audited."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle billing: invoice and balance consultation, and payment-deferral. "
                "For the caller's own invoice or balance, use get_invoice_summary / "
                "get_balance_summary. For general offer/procedure/FAQ questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. Keep replies short. NEVER claim a payment or "
                "deferral succeeded yourself - only the tool result decides that. If a tool "
                "result is 'refused', explain the reason plainly. If it is 'escalate', explain "
                "briefly and call escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[
                get_invoice_summary,
                get_balance_summary,
                request_payment_deferral,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the billing question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their billing question, in their language.",
        )