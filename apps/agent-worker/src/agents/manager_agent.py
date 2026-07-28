"""ManagerAgent: escalation target — transfer or callback, and open a follow-up ticket (Phase 9).

Inherits BaseTelecomAgent. Reached on the shared session (full context). Can open a ticket so an
escalated issue is tracked and the caller gets a written confirmation.
"""

from __future__ import annotations

from providers.tts import build_persona_tts
from telephony.sip_transfer import transfer_to_human
from tools.ticket_tools import (
    check_customer_tickets,
    create_support_ticket,
    get_ticket_state,
)

from agents.base_agent import (
    CLOSING_PROTOCOL,
    LANGUAGE_SWITCH_POLICY,
    BaseTelecomAgent,
)

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer/callback, plus follow-up ticketing."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            instructions="\n".join([
                (
                    f"You are a senior support manager handling an escalated call. You MUST speak ONLY in {lang_name}. Never switch language.\n"
                    "Call transfer_to_human immediately and do not speak before calling it. "
                    "The transfer tool owns the single transition announcement and will schedule a callback "
                    "if none is free). Ticketing is optional and only when it helps: if the caller "
                    "asks about a ticket, or the issue needs tracking, you MAY call "
                    "check_customer_tickets to see existing ones, and create_support_ticket only "
                    "if none covers the issue - then give them the reference. Never invent a "
                    "ticket or status, and if a ticket tool returns 'unavailable', say honestly "
                    "you cannot reach the ticketing system right now. "
                    "Never tell the caller to call another department or another number yourself: "
                    "you are the final escalation point, so either transfer_to_human, arrange the "
                    "callback the tool schedules, or track the issue with a ticket. "
                    f"Keep replies short and calm; always reply in {lang_name}."
                ),
                CLOSING_PROTOCOL,
                LANGUAGE_SWITCH_POLICY,
                "\n\nIMPORTANT: You MUST speak ONLY in the language already specified above. Never switch.",
            ]),
            chat_ctx=chat_ctx,
            tools=[
                transfer_to_human,
                create_support_ticket,
                check_customer_tickets,
                get_ticket_state,
            ],
            language=selected_language,
            tts=build_persona_tts(selected_language, "manager"),
        )
        self._language = selected_language
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Start the transfer without generating a second transition message."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is not None:
            lang = getattr(user_data, "language", self._language)
            lang_code = getattr(lang, "value", lang) if lang else self._language
            if isinstance(lang_code, str) and lang_code.lower().strip()[:2] in _LANG_NAMES:
                self._language = lang_code.lower().strip()[:2]
                self._lang_name = _LANG_NAMES[self._language]

        await self.session.generate_reply(
            instructions=(
                f"In {self._lang_name} only: briefly introduce yourself as a senior "
                f"advisor, ACKNOWLEDGE the reason the call was escalated (using the "
                f"conversation so far), and ask how you can help resolve it. Two short "
                f"sentences. Be empathetic. Do NOT repeat information already given. "
                f"Never switch language."
            ),
        )
