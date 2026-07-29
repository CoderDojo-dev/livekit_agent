"""BillingAgent: bill consultation (read), payment + payment-deferral (guarded) (CDC 5.1-5.3).

Phase 7: make_payment confirms the amount (PaymentConfirmTask) then runs the full
Decision -> Policy -> Execution façade; an AUTHORIZED action is dispatched idempotently and the
caller is given the confirmation reference. Deferral runs the same façade.
"""

from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from providers.tts import build_persona_tts
from tasks.payment_confirm_task import PaymentConfirmTask
from tools import outcomes
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified
from tools.voice_flow import active_persona_tts

from agents.base_agent import BaseTelecomAgent

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}

# Persona core, module level so it can be imported and asserted by tests without
# building a TTS provider. Text identical to v63.
_CORE = (
    "You handle billing: invoice/balance consultation, payment, and payment-deferral. "
    "You MUST speak ONLY in {lang_name}. Never switch to another language.\n"
    "For the caller's own invoice or balance, use get_invoice_summary / "
    "get_balance_summary. To take a payment use make_payment; for a deferral use "
    "request_payment_deferral. For general offer/procedure/FAQ questions, call "
    "knowledge_search with a concise ENGLISH query and answer in {lang_name}, "
    "citing the source. Keep replies short. NEVER claim a payment or "
    "deferral succeeded yourself - only the tool result decides. Communicate the "
    "tool's 'message' to the caller: on 'executed' give the reference; on 'refused' "
    "or 'failed' explain plainly; on 'escalate' explain briefly and call "
    "escalate_to_manager. Always reply in {lang_name}."
)


async def _outstanding_total(context: RunContext) -> float:
    """The amount currently owed by this caller, across all unpaid invoices."""
    user_data = context.session.userdata
    if user_data.customer_context is None:
        return 0.0
    invoices = await get_context_client().get_invoices(user_data.customer_context.customer_id)
    return sum(
        inv.get("outstanding", inv["amount"]) for inv in invoices if inv.get("status") != "paid"
    )


@function_tool()
async def make_payment(context: RunContext, amount: float) -> dict:
    """Take a bill payment of ``amount`` TND (CDC section 5.2).

    Identity-gated -> explicit amount confirmation -> Decision/Policy/Execution. Returns a
    standard outcome ('executed' with a reference, 'refused', 'escalate', or 'failed').
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    confirmed = await PaymentConfirmTask(amount=amount, tts=active_persona_tts(context))
    unpaid_amount = await _outstanding_total(context)
    return await execute_guarded_action(
        context,
        "EXECUTE_PAYMENT",
        {"amount": amount, "unpaid_amount": unpaid_amount, "payment_confirmed": bool(confirmed)},
    )


@function_tool()
async def request_payment_deferral(context: RunContext, requested_days: int) -> dict:
    """Request a payment deferral of ``requested_days`` days (CDC section 5.3).

    Identity-gated, then Decision -> Policy -> Execution. Returns a standard outcome.
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")

    unpaid_amount = await _outstanding_total(context)
    return await execute_guarded_action(
        context,
        "PAYMENT_DEFERRAL",
        # deferrals_this_year is deliberately NOT sent: the agent has no access to the deferral
        # history, and a fabricated 0 disabled the DEF_CAP rule. Policy counts it from its own
        # action ledger (the only source of truth) and fails closed if it cannot.
        {"requested_days": requested_days, "unpaid_amount": unpaid_amount},
    )


class BillingAgent(BaseTelecomAgent):
    """Concentrates billing/payment risk. Reads are free; sensitive writes are guarded + audited."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        from tools.routing_tools import route_to_account_services, route_to_technical

        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            core_instructions=_CORE.format(lang_name=lang_name),
            capabilities={"knowledge_search"},
            chat_ctx=chat_ctx,
            tools=[
                get_invoice_summary,
                get_balance_summary,
                make_payment,
                request_payment_deferral,
                route_to_account_services,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
            tts=build_persona_tts(selected_language, "billing"),
        )
        self._language = selected_language
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the billing question in the locked language."""
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
                f"specific billing matter the caller already mentioned earlier (e.g. "
                f"an invoice, balance, or payment) and ask them to confirm the detail. "
                f"If nothing specific was mentioned yet, simply ask how you can help "
                f"with their billing question. One or two short sentences. Do NOT "
                f"repeat information already given. Never switch language."
            ),
        )
