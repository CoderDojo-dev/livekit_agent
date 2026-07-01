"""BillingAgent: bill consultation, payment, payment-deferral (CDC sections 5.1-5.3).

Phase 4 wires one identity-gated sensitive attempt (payment deferral) to prove the identity
gate fires before any domain action. The Decision -> Policy -> Execution of the deferral
itself lands in Phase 7; here the tool stops at the verified-but-not-yet-executed boundary.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

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
    """Concentrates billing/payment risk. Sensitive tools are identity-gated."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle billing: invoice consultation, payment, and payment-deferral. "
                "Keep replies short and natural for speech. NEVER claim a payment or deferral "
                "succeeded yourself - only a tool result determines that. If a tool result is "
                "'escalate', explain plainly and call escalate_to_manager. "
                "Always reply in the caller's current language."
            ),
            chat_ctx=chat_ctx,
            tools=[request_payment_deferral, escalate_to_manager],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the billing question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their billing question, in their language.",
        )