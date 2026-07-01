"""BillingAgent: bill consultation (read), payment-deferral (identity-gated) (CDC 5.1-5.3).

Phase 5 adds read-only invoice/balance tools and the scoped knowledge_search toolset.
The deferral's Decision -> Policy -> Execution lands in Phase 7; here it stops at the
verified boundary.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from mcp_clients.knowledge_glpi_toolset import build_knowledge_toolset
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager
from tools.guards import ensure_identity_verified


@function_tool()
async def request_payment_deferral(context: RunContext, requested_days: int) -> dict:
    """Request a payment deferral of the given number of days (CDC section 5.3). Identity-gated:
    runs step-up verification first; the actual deferral executes in Phase 7."""
    if not await ensure_identity_verified(context):
        return {"outcome": "escalate", "reason": "identity_not_verified"}
    return {
        "outcome": "identity_verified",
        "next": "deferral_pending_execution_phase_7",
        "requested_days": requested_days,
    }


class BillingAgent(Agent):
    """Concentrates billing/payment risk. Reads are free; sensitive writes are identity-gated."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle billing: invoice and balance consultation, and payment-deferral. "
                "For the caller's own invoice or balance, use get_invoice_summary / "
                "get_balance_summary. For general questions about offers, procedures, or FAQs, "
                "call knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. Keep replies short. NEVER claim a payment or "
                "deferral succeeded yourself - only a tool result determines that. If a tool "
                "result is 'escalate', explain plainly and call escalate_to_manager. "
                "Always reply in the caller's current language."
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