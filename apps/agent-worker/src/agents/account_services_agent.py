"""AccountServicesAgent (CDC 5.6-5.8): plan consultation/change, prepaid recharge, roaming.

Inherits BaseTelecomAgent so it gets the shared per-turn sentiment scoring + proactive
de-escalation + conversation logging, like every other persona. All state changes go through the
guarded action path.
"""

from __future__ import annotations

from mcp_clients.knowledge_toolset import build_knowledge_toolset
from providers.tts import build_persona_tts
from tools.account_tools import change_plan, get_plan_details, toggle_roaming, top_up
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager

from agents.base_agent import KNOWLEDGE_ABSTENTION_RULE, BaseTelecomAgent

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}

_CORE = (
    "You handle account services: plan consultation, plan changes, prepaid recharges, "
    "and roaming. You MUST speak ONLY in {lang_name}. Never switch to another language.\n"
    "For the current plan call get_plan_details. To change a plan use "
    "change_plan. For a recharge use top_up. For roaming use toggle_roaming. "
    "For balance or invoice queries use get_balance_summary / get_invoice_summary "
    "(read-only; payments and deferrals still need route_to_billing). If the "
    "caller is upset or asks for a human, call escalate_to_manager. "
    "Keep replies short.\n\n"
    + KNOWLEDGE_ABSTENTION_RULE
)


class AccountServicesAgent(BaseTelecomAgent):
    """Lower-risk account-management persona; every state change is verdict-checked + audited."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        from tools.routing_tools import route_to_billing, route_to_technical

        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            core_instructions=_CORE.format(lang_name=lang_name),
            capabilities={"knowledge_search"},
            chat_ctx=chat_ctx,
            tools=[
                get_plan_details,
                change_plan,
                top_up,
                toggle_roaming,
                get_balance_summary,
                get_invoice_summary,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
            tts=build_persona_tts(selected_language, "account"),
        )
        self._language = selected_language
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Greet briefly and invite the account-management request in the locked language."""
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
                f"specific request the caller already mentioned earlier (plan, phone "
                f"line, recharge, or roaming) and ask them to confirm the detail. If "
                f"nothing specific was mentioned yet, simply ask how you can help with "
                f"plans, recharges, or roaming. One or two short sentences. Do NOT "
                f"repeat information already given. Never switch language."
            ),
        )
