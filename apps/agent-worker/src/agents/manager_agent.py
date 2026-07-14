"""ManagerAgent: escalation target — transfer or callback, and open a follow-up ticket (Phase 9).

Inherits BaseTelecomAgent. Reached on the shared session (full context). Can open a ticket so an
escalated issue is tracked and the caller gets a written confirmation.
"""
from __future__ import annotations

from mcp_clients.ticketing_toolset import build_ticketing_toolset
from telephony.sip_transfer import transfer_to_human

from agents.base_agent import BaseTelecomAgent

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer/callback, plus follow-up ticketing."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            instructions=(
                f"You are a senior support manager handling an escalated call. You MUST speak ONLY in {lang_name}. Never switch language.\n"
                "Call transfer_to_human immediately and do not speak before calling it. "
                "The transfer tool owns the single transition announcement and will schedule a callback "
                "if none is free). If the issue needs tracking, call create_ticket (with the "
                "caller's language) so they receive a written confirmation, and give them the "
                f"reference. Keep replies short and calm; always reply in {lang_name}."
            ),
            chat_ctx=chat_ctx,
            tools=[transfer_to_human, build_ticketing_toolset()],
            language=selected_language,
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

        self.session.generate_reply(
            instructions=(
                f"In {self._lang_name} only, call transfer_to_human now. Do not produce spoken text before the tool call."
            ),
        )
