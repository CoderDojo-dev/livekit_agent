"""Schedule a callback when no advisor is free (CDC 5.12 / 6.4). Bounded + never silent."""
from __future__ import annotations

import asyncio
import logging

from clients.notification_client import get_notification_client
from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

CALLBACK_DEADLINE_S = 25.0  # no clear answer within this -> no callback scheduled


class CallbackScheduleTask(AgentTask[bool]):
    """Offers a callback, records the preferred time, texts a confirmation. Never hangs."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "No advisor is available right now. Apologize briefly, offer the caller a "
                "callback, and ask for a preferred time window. Record it, or note if they "
                "decline. Always speak in the caller's language."
            ),
            chat_ctx=chat_ctx,
        )
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        self._arm()
        try:
            await self.session.generate_reply(instructions=(
                "Apologize that no advisor is free, offer a callback, and ask for a preferred "
                "time window, in the caller's language."
            ))
        except Exception as exc:
            logger.warning("callback prompt failed: %s", exc)
            await self._fail_closed()

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(CALLBACK_DEADLINE_S)
        except asyncio.CancelledError:
            return
        await self._fail_closed()

    async def _fail_closed(self) -> None:
        if self._done:
            return
        logger.info("callback fail-closed -> no callback scheduled")
        try:
            await self.session.say(
                "Je n'ai pas pu programmer de rappel pour le moment. N'hésitez pas à rappeler."
            )
        except Exception:
            pass
        self._finish(False)

    def _finish(self, scheduled: bool) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        self.complete(scheduled)

    @function_tool()
    async def record_callback(self, preferred_time: str) -> None:
        """Record the caller's preferred callback time window and send a written confirmation."""
        user_data = self.session.userdata
        user_data.callback_requested = True
        user_data.callback_when = preferred_time

        customer = user_data.customer_context
        if customer is not None:
            try:
                await get_notification_client().notify(
                    customer.customer_id,
                    "callback_scheduled",
                    user_data.language,
                    {"when": preferred_time},
                )
            except Exception as exc:
                logger.warning("callback notify failed (continuing): %s", exc)

        writer = getattr(user_data, "conversation_writer", None)
        if writer is not None:
            try:
                writer.record_callback(
                    customer_id=customer.customer_id if customer else None,
                    subscription_id=getattr(customer, "subscription_id", None) if customer else None,
                )
            except Exception as exc:
                logger.debug("callback log skipped: %s", exc)
        self._finish(True)

    @function_tool()
    async def decline_callback(self) -> None:
        """Record that the caller declined a callback."""
        self._finish(False)
