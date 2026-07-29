"""ManagerAgent: escalation target - transfer or callback, and open a follow-up ticket (Phase 9).

Inherits BaseTelecomAgent. Reached on the shared session (full context). Can open a ticket so an
escalated issue is tracked and the caller gets a written confirmation.

on_enter runs the transfer ITSELF instead of asking the LLM to speak: the escalating tool has
already announced the transfer, so a generated turn here could only duplicate or contradict it.
"""

from __future__ import annotations

import logging

from livekit.agents.llm.tool_context import StopResponse
from providers.tts import build_persona_tts
from telephony.sip_transfer import transfer_to_human
from tools.ticket_tools import (
    check_customer_tickets,
    create_support_ticket,
    get_ticket_state,
)

from agents.base_agent import BaseTelecomAgent

logger = logging.getLogger(__name__)

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}

_CORE = (
    "You are a senior support manager handling an escalated call. You MUST speak ONLY in {lang_name}. Never switch language.\n"
    "Call transfer_to_human immediately and do not speak before calling it. "
    "The transfer tool owns the single transition announcement and will schedule "
    "a callback if no advisor is free. "
    "PRIORITY ORDER: the transfer comes FIRST. Only once the transfer tool has "
    "answered with a callback outcome do the ticketing and closing rules below "
    "apply. Never open a ticket and never end the call before the transfer tool "
    "has answered. "
    "Ticketing is optional and only when it helps: if the caller "
    "asks about a ticket, or the issue needs tracking, you MAY call "
    "check_customer_tickets to see existing ones, and create_support_ticket only "
    "if none covers the issue - then give them the reference. Never invent a "
    "ticket or status, and if a ticket tool returns 'unavailable', say honestly "
    "you cannot reach the ticketing system right now. "
    "Never tell the caller to call another department or another number yourself: "
    "you are the final escalation point, so either transfer_to_human, arrange the "
    "callback the tool schedules, or track the issue with a ticket. "
    "Keep replies short and calm; always reply in {lang_name}."
)


class _TransferContext:
    """Minimal RunContext stand-in so on_enter can run the transfer with no LLM turn.

    transfer_to_human only ever reads ``context.session`` and optionally calls
    ``context.disallow_interruptions()`` (already exception-guarded on its side).
    Nothing else of RunContext is used, so a two-attribute shim is sufficient and
    keeps the tool itself unchanged for the LLM path.
    """

    __slots__ = ("session",)

    def __init__(self, session) -> None:
        self.session = session

    def disallow_interruptions(self) -> None:
        """No-op: outside a tool turn there is no generated speech to protect."""
        return None


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer/callback, plus follow-up ticketing."""

    def __init__(self, chat_ctx=None, language: str = "fr") -> None:
        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]
        super().__init__(
            core_instructions=_CORE.format(lang_name=lang_name),
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

        try:
            result = await transfer_to_human(_TransferContext(self.session))
        except StopResponse:
            # Transfer succeeded: the caller's leg has been REFERred away. Saying
            # anything now would be speech into an empty room.
            return
        except Exception as exc:
            logger.warning("manager transfer attempt failed: %s", exc)
            result = {"outcome": "failed"}

        outcome = (result or {}).get("outcome")
        logger.info("manager transfer outcome=%s", outcome)
        if outcome == "transferred":
            return

        # Callback scheduled / declined / failed: the tool already spoke the facts.
        # ONE short wrap-up turn, driven by the tool's own message - never invented.
        guidance = (result or {}).get("message") or (
            "Say plainly that the transfer could not be completed and that they may call back."
        )
        await self.session.generate_reply(
            instructions=(
                f"In {self._lang_name} only, in at most two short sentences: {guidance} "
                "Then ask whether there is anything else you can help with. Do not promise "
                "a transfer again and do not invent any detail. Never switch language."
            ),
        )
