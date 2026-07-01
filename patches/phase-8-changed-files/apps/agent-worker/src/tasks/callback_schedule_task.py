"""Schedule a callback when no advisor is free (CDC section 5.12 / 6.4).

Records the caller's preferred time window in session user-data. The written confirmation
(SMS/Email) is sent by the notification-service in Phase 9; here we capture the request and
confirm it verbally.
"""
from __future__ import annotations

from livekit.agents import AgentTask, function_tool


class CallbackScheduleTask(AgentTask[bool]):
    """Offers a callback and records the preferred time; returns True if one was scheduled."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "No advisor is available right now. Apologize briefly, offer the caller a "
                "callback, and ask for a preferred time window. Record it, or note if they "
                "decline. Always speak in the caller's language."
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        """Offer the callback and ask for a preferred time."""
        await self.session.generate_reply(
            instructions=(
                "Apologize that no advisor is free, offer a callback, and ask for a preferred "
                "time window, in the caller's language."
            ),
        )

    @function_tool()
    async def record_callback(self, preferred_time: str) -> None:
        """Record the caller's preferred callback time window."""
        user_data = self.session.userdata
        user_data.callback_requested = True
        user_data.callback_when = preferred_time
        self.complete(True)

    @function_tool()
    async def decline_callback(self) -> None:
        """Record that the caller declined a callback."""
        self.complete(False)