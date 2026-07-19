"""TechnicalAgent: SIM / network / connectivity (CDC section 5.5) + ticketing (Phase 9).

Inherits BaseTelecomAgent (sentiment-aware). Can open a follow-up ticket for an unresolved
issue (the caller then gets a written confirmation) and resolve it if solved during the call.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.sim_replacement_task_group import SimReplacementTaskGroup
from tools import outcomes
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified
from tools.technical_tools import check_network_status, diagnose_data_issue
from tools.ticket_tools import (
    check_customer_tickets,
    create_support_ticket,
    get_ticket_state,
    mark_ticket_resolved,
    update_support_ticket,
)

from agents.base_agent import BaseTelecomAgent, KNOWLEDGE_ABSTENTION_RULE

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


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

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        from tools.routing_tools import route_to_account_services, route_to_billing

        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            instructions=(
                f"You handle technical issues: SIM problems, network and connectivity. "
                f"You MUST speak ONLY in {lang_name}. Never switch to another language.\n"
                "To unblock a SIM, use unblock_sim. To request a SIM replacement, use replace_sim. "
                "To diagnose a data/connectivity complaint, use diagnose_data_issue. "
                "To check known incidents for an area, use check_network_status. "
                "For how-to/known-issue questions, call knowledge_search with a concise "
                f"ENGLISH query and answer in {lang_name}, citing the source. "
                "When a caller describes a problem, FIRST call check_customer_tickets: "
                "if an open ticket already covers it, reassure them it is registered "
                "and being handled; if a matching ticket is now resolved, tell them "
                "the good news. If an issue cannot be solved on the call and no ticket "
                "covers it, call create_support_ticket (subject + short description) so "
                "the caller gets a written confirmation; give them the ticket reference. "
                "If the issue IS solved during the call, call mark_ticket_resolved. "
                "To check one ticket use get_ticket_state; to amend one use "
                "update_support_ticket. Never invent a ticket or a status. Keep replies short. "
                "NEVER claim an operation succeeded yourself - only the tool result decides. "
                "If a result is 'refused' or 'failed', communicate its 'message' plainly; "
                f"if 'escalate', call escalate_to_manager. Always reply in {lang_name}."
                + "\n\n" + KNOWLEDGE_ABSTENTION_RULE
            ),
            chat_ctx=chat_ctx,
            tools=[
                unblock_sim,
                replace_sim,
                diagnose_data_issue,
                check_network_status,
                route_to_account_services,
                route_to_billing,
                escalate_to_manager,
                create_support_ticket,
                check_customer_tickets,
                get_ticket_state,
                mark_ticket_resolved,
                update_support_ticket,
                build_knowledge_toolset(),
            ],
        )
        self._language = selected_language
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the technical question in the locked language."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is not None:
            lang = getattr(user_data, "language", self._language)
            lang_code = getattr(lang, "value", lang) if lang else self._language
            if isinstance(lang_code, str) and lang_code.lower().strip()[:2] in _LANG_NAMES:
                self._language = lang_code.lower().strip()[:2]
                self._lang_name = _LANG_NAMES[self._language]

        await self.session.generate_reply(
            instructions=(
                f"In {self._lang_name} only, ask the caller how you can help with their "
                f"technical issue. One short sentence. Never switch language."
            ),
        )
