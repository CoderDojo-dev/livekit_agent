"""TechnicalAgent: SIM / network / connectivity (CDC section 5.5).

Phase 7 wires the SIM write path: unblock_sim is identity-gated then runs the full
Decision -> Policy -> Execution façade (SIM operations require prior identity verification, CDC 6.3).
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tools import outcomes
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified


@function_tool()
async def unblock_sim(context: RunContext) -> dict:
    """Unblock the caller's SIM card (CDC section 5.5). Identity-gated, then guarded + executed."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "UNBLOCK_SIM", {})


class TechnicalAgent(Agent):
    """Concentrates SIM/network risk. Sensitive operations are identity-gated and guarded."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle technical issues: SIM problems, network and connectivity. "
                "To unblock a SIM, use unblock_sim. For how-to/known-issue questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. Keep replies short. NEVER claim an operation "
                "succeeded yourself - only the tool result decides. If a tool result is "
                "'refused' or 'failed', communicate its 'message' plainly; if 'escalate', "
                "explain briefly and call escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[unblock_sim, escalate_to_manager, build_knowledge_toolset()],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the technical question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their technical issue, in their language.",
        )