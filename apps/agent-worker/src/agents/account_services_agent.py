"""AccountServicesAgent (CDC 5.6-5.8): plan consultation/change, prepaid recharge, roaming.

Inherits BaseTelecomAgent so it gets the shared per-turn sentiment scoring + proactive
de-escalation + conversation logging, like every other persona. All state changes go through the
guarded action path.
"""
from __future__ import annotations

from tools.account_tools import change_plan, get_plan_details, toggle_roaming, top_up
from tools.escalation_tools import escalate_to_manager

from agents.base_agent import BaseTelecomAgent

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


class AccountServicesAgent(BaseTelecomAgent):
    """Lower-risk account-management persona; every state change is verdict-checked + audited."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            instructions=(
                f"You handle account services: plan consultation, plan changes, prepaid recharges, "
                f"and roaming. You MUST speak ONLY in {lang_name}. Never switch to another language.\n"
                "For the current plan call get_plan_details. To change a plan use "
                "change_plan. For a recharge use top_up. For roaming use toggle_roaming. If the "
                "caller is upset or asks for a human, call escalate_to_manager. Keep replies short."
            ),
            chat_ctx=chat_ctx,
            tools=[get_plan_details, change_plan, top_up, toggle_roaming, escalate_to_manager],
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
                f"In {self._lang_name} only, ask the caller how you can help with plans, "
                f"recharges, or roaming. One short sentence. Never switch language."
            ),
        )