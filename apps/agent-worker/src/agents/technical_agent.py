"""TechnicalAgent: SIM / network / connectivity (CDC section 5.5) + ticketing (Phase 9).

Inherits BaseTelecomAgent (sentiment-aware). Can open a follow-up ticket for an unresolved
issue (the caller then gets a written confirmation) and resolve it if solved during the call.
"""

from __future__ import annotations

from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from providers.tts import build_persona_tts
from tasks.sim_replacement_task_group import SimReplacementTaskGroup
from tools import outcomes
from tools.escalation_tools import caller_refused_manager, escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified
from tools.technical_tools import check_network_status, diagnose_data_issue
from tools.ticket_tools import (
    check_customer_tickets,
    create_support_ticket,
    delete_support_ticket,
    get_ticket_state,
    mark_ticket_resolved,
    update_support_ticket,
)
from tools.voice_flow import active_persona_tts

from agents.base_agent import BaseTelecomAgent

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}

_CORE = (
    "You handle technical issues: SIM problems, network and connectivity. "
    "You MUST speak ONLY in {lang_name}. Never switch to another language.\n"
    "To unblock a SIM, use unblock_sim. To request a SIM replacement, use replace_sim. "
    "To diagnose a data/connectivity complaint, use diagnose_data_issue. "
    "To check known incidents for an area, use check_network_status. "
    "Place names are often mis-transcribed: if check_network_status "
    "returns 'needs_area_confirmation', do NOT conclude anything - ask "
    "the caller to confirm the candidate area by name, or to repeat or "
    "spell it, offering the suggestions as a question. "
    "For how-to/known-issue questions, call knowledge_search with a concise "
    "ENGLISH query and answer in {lang_name}, citing the source. "
    "Ticketing is not small talk - never bring it up spontaneously. But when it is "
    "relevant, it is MANDATORY, not optional:\n"
    "- The FIRST time the caller reports a concrete problem that is not solved on "
    "this call, you MUST call check_customer_tickets BEFORE anything else about "
    "tickets. If an open ticket covers it, give its reference and tell them it is "
    "being handled. If nothing matches, offer to open one.\n"
    "- When the caller says a problem is SOLVED, or asks to close/cancel a ticket, "
    "you MUST call mark_ticket_resolved with resolution filled and ticket_id LEFT "
    "EMPTY. The tool finds their open ticket itself. If it answers "
    "'needs_selection', read the subjects and ask which one. If it answers "
    "'nothing_to_resolve', simply say they have no open ticket.\n"
    "- When the caller asks about a ticket or its progress, use "
    "check_customer_tickets, or get_ticket_state when they give a reference.\n"
    "- Call create_support_ticket only for a problem that cannot be solved now. If "
    "it answers 'duplicate_candidate', do NOT create anything: give the existing "
    "reference and ask whether they want a separate ticket; only if they say yes, "
    "call it again with confirm_new true.\n"
    "- To correct a ticket use update_support_ticket. To withdraw one opened by "
    "mistake use delete_support_ticket; if it answers 'refused' because the ticket "
    "is resolved or closed, explain it stays in their history.\n"
    "- If any ticket tool answers 'refused', never argue and never reveal details: "
    "ask the caller to confirm their own reference.\n"
    "\n"
    "Network status: you may state that the network is normal ONLY when check_network_status "
    "returned did_verify true AND incident_found false. If the result is 'unavailable' or "
    "'area_unknown', you have verified NOTHING: say so plainly and ask for the exact area or "
    "offer a follow-up. Never reassure a caller about a network you did not check. "
)


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

    details = await SimReplacementTaskGroup(tts=active_persona_tts(context))
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
            core_instructions=_CORE.format(lang_name=lang_name),
            capabilities={"knowledge_search"},
            chat_ctx=chat_ctx,
            tools=[
                unblock_sim,
                replace_sim,
                diagnose_data_issue,
                check_network_status,
                route_to_account_services,
                route_to_billing,
                escalate_to_manager,
                caller_refused_manager,
                create_support_ticket,
                check_customer_tickets,
                get_ticket_state,
                mark_ticket_resolved,
                update_support_ticket,
                delete_support_ticket,
                build_knowledge_toolset(),
            ],
            tts=build_persona_tts(selected_language, "technical"),
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
                f"In {self._lang_name} only: greet briefly, then ACKNOWLEDGE the "
                f"specific technical problem the caller already described earlier in "
                f"the conversation (e.g. a network or SIM issue) and ask them to give "
                f"a bit more detail about it. If NO specific problem was mentioned "
                f"yet, simply ask how you can help with their technical issue. One or "
                f"two short sentences. Do NOT repeat information already given. Never "
                f"switch language."
            ),
        )
