"""TechnicalAgent: SIM / network / connectivity (CDC section 5.5) + ticketing (Phase 9).

Inherits BaseTelecomAgent (sentiment-aware). Can open a follow-up ticket for an unresolved
issue (the caller then gets a written confirmation) and resolve it if solved during the call.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from mcp_clients.ticketing_toolset import build_ticketing_toolset
from tasks.sim_replacement_task_group import SimReplacementTaskGroup
from tools import outcomes
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified

from agents.base_agent import BaseTelecomAgent


@function_tool()
async def unblock_sim(context: RunContext) -> dict:
    """Unblock the caller's SIM card (CDC section 5.5). Identity-gated, then guarded + executed."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "UNBLOCK_SIM", {})


@function_tool()
async def replace_sim(context: RunContext) -> dict:
    """Request a SIM replacement (CDC section 5.5). Identity-gated, detail-collected, guarded."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")

    details = await SimReplacementTaskGroup()
    if not details:
        return outcomes.escalate(
            "SIM_REPLACEMENT_INCOMPLETE",
            "SIM replacement details were not confirmed",
        )

    return await execute_guarded_action(context, "REPLACE_SIM", details)


class TechnicalAgent(BaseTelecomAgent):
    """Concentrates SIM/network risk. Sensitive ops are identity-gated; opens/resolves tickets."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle technical issues: SIM problems, network and connectivity. "
                "To unblock a SIM, use unblock_sim. To request a SIM replacement, use replace_sim. "
                "For how-to/known-issue questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. If an issue cannot be solved on the call, call "
                "create_ticket (subject + short description + the caller's language) so the "
                "caller gets a written confirmation; give them the ticket reference. If the "
                "issue IS solved during the call, you may resolve_ticket. Keep replies short. "
                "NEVER claim an operation succeeded yourself - only the tool result decides. "
                "If a result is 'refused' or 'failed', communicate its 'message' plainly; if "
                "'escalate', call escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[
                unblock_sim,
                replace_sim,
                escalate_to_manager,
                build_knowledge_toolset(),
                build_ticketing_toolset(),
            ],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the technical question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their technical issue, in their language.",
        )