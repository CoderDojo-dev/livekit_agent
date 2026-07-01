"""BillingAgent: bill consultation (read), payment + payment-deferral (guarded) (CDC 5.1-5.3).

Phase 7: make_payment confirms the amount (PaymentConfirmTask) then runs the full
Decision -> Policy -> Execution façade; an AUTHORIZED action is dispatched idempotently and the
caller is given the confirmation reference. Deferral runs the same façade.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from clients.context_client import get_context_client
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.payment_confirm_task import PaymentConfirmTask
from tools import outcomes
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified


@function_tool()
async def make_payment(context: RunContext, amount: float) -> dict:
    """Take a bill payment of ``amount`` TND (CDC section 5.2).

    Identity-gated -> explicit amount confirmation -> Decision/Policy/Execution. Returns a
    standard outcome ('executed' with a reference, 'refused', 'escalate', or 'failed').
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    confirmed = await PaymentConfirmTask(amount=amount)
    return await execute_guarded_action(
        context, "EXECUTE_PAYMENT", {"amount": amount, "payment_confirmed": bool(confirmed)}
    )


@function_tool()
async def request_payment_deferral(context: RunContext, requested_days: int) -> dict:
    """Request a payment deferral of ``requested_days`` days (CDC section 5.3).

    Identity-gated, then Decision -> Policy -> Execution. Returns a standard outcome.
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")

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
                "You handle billing: invoice/balance consultation, payment, and payment-deferral. "
                "For the caller's own invoice or balance, use get_invoice_summary / "
                "get_balance_summary. To take a payment use make_payment; for a deferral use "
                "request_payment_deferral. For general offer/procedure/FAQ questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. Keep replies short. NEVER claim a payment or "
                "deferral succeeded yourself - only the tool result decides. Communicate the "
                "tool's 'message' to the caller: on 'executed' give the reference; on 'refused' "
                "or 'failed' explain plainly; on 'escalate' explain briefly and call "
                "escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[
                get_invoice_summary,
                get_balance_summary,
                make_payment,
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