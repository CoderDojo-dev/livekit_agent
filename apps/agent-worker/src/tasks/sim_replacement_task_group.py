"""Multi-step SIM replacement collection (CDC 5.5).

Bounded + fail-closed: collects the reason, delivery/contact details, then returns
a payload for the guarded REPLACE_SIM action. If the caller is unclear or silent,
the task completes with None so no replacement is executed silently.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

SIM_REPLACEMENT_DEADLINE_S = 45.0


class SimReplacementTaskGroup(AgentTask[dict | None]):
    """Collect replacement reason + delivery/contact details. Never hangs."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Collect the information needed for a SIM replacement. Ask for: "
                "1) the reason for replacement, 2) the delivery address or pickup preference, "
                "3) a contact phone number, and optionally 4) preferred delivery time window. "
                "Be brief, ask in the caller's language, and do not execute anything yourself. "
                "Once you have the details, call record_sim_replacement_details."
            ),
            chat_ctx=chat_ctx,
        )
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        self._arm()
        try:
            await self.session.generate_reply(
                instructions=(
                    "Tell the caller you can help start a SIM replacement request. "
                    "Ask briefly for the reason, delivery address or pickup preference, "
                    "and a contact phone number, in their language."
                )
            )
        except Exception as exc:
            logger.warning("sim replacement prompt failed: %s", exc)
            await self._fail_closed("prompt_error")

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(SIM_REPLACEMENT_DEADLINE_S)
        except asyncio.CancelledError:
            return
        await self._fail_closed("timeout")

    async def _fail_closed(self, reason: str) -> None:
        if self._done:
            return
        logger.info("sim replacement fail-closed (%s) -> no replacement request", reason)
        with suppress(Exception):
            await self.session.say(
                "Je n'ai pas reçu toutes les informations nécessaires, je ne lance pas le remplacement de SIM."
            )
        self._finish(None)

    def _finish(self, payload: dict | None) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        self.complete(payload)

    @function_tool()
    async def record_sim_replacement_details(
        self,
        reason: str,
        delivery_address: str,
        contact_phone: str,
        preferred_delivery_window: str | None = None,
    ) -> None:
        """Record the details needed to request a SIM replacement."""
        self._arm()

        reason = (reason or "").strip()
        delivery_address = (delivery_address or "").strip()
        contact_phone = (contact_phone or "").strip()
        preferred_delivery_window = (preferred_delivery_window or "").strip() or None

        if not reason or not delivery_address or not contact_phone:
            try:
                await self.session.generate_reply(
                    instructions=(
                        "Explain briefly that some required details are missing, then ask again "
                        "for the missing SIM replacement reason, delivery address or pickup "
                        "preference, and contact phone number, in the caller's language."
                    )
                )
            except Exception as exc:
                logger.warning("sim replacement re-prompt failed: %s", exc)
                await self._fail_closed("reprompt_error")
            return

        payload = {
            "reason": reason,
            "delivery_address": delivery_address,
            "contact_phone": contact_phone,
            "preferred_delivery_window": preferred_delivery_window,
            "delivery_confirmed": True,
        }

        with suppress(Exception):
            await self.session.say(
                "Merci, j'ai les informations nécessaires pour lancer la demande de remplacement de SIM."
            )

        self._finish(payload)

    @function_tool()
    async def cancel_sim_replacement(self) -> None:
        """Record that the caller does not want to continue the SIM replacement request."""
        with suppress(Exception):
            await self.session.say("D'accord, je ne lance pas de remplacement de SIM.")
        self._finish(None)
