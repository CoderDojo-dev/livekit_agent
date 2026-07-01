"""Step-up identity verification (CDC section 6.5; Blueprint section 10.1).

Runs inline the first time a sensitive action is attempted. Counts failed attempts and, on
the configured maximum, completes False so the caller flow escalates to a human
(repeated identity failure is a mandatory-escalation trigger). The secret is checked by the
injected verify_fn (the context-service), never held in the task.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from livekit.agents import AgentTask, function_tool

MAX_ATTEMPTS = 3


class IdentityVerificationTask(AgentTask[bool]):
    """Takes over the session until the caller is verified or attempts are exhausted."""

    def __init__(
        self,
        customer_id: str,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        chat_ctx=None,
    ) -> None:
        super().__init__(
            instructions=(
                "Before proceeding with this sensitive request, verify the caller's identity. "
                "Ask the caller for the last four digits of their national ID (CIN). "
                "Always speak in the caller's current language. Be brief and reassuring."
            ),
            chat_ctx=chat_ctx,
        )
        self._customer_id = customer_id
        self._verify_fn = verify_fn
        self._attempts = 0

    async def on_enter(self) -> None:
        """Prompt the caller for the known personal element."""
        await self.session.generate_reply(
            instructions=(
                "Ask the caller to verify their identity by stating the last four digits of "
                "their national ID, in their language."
            ),
        )

    @function_tool()
    async def verify_with_known_element(self, provided_value: str) -> None:
        """Verify the caller's identity using the value they provided (last 4 digits of CIN)."""
        self._attempts += 1
        if await self._verify_fn(self._customer_id, provided_value):
            self.complete(True)
        elif self._attempts >= MAX_ATTEMPTS:
            self.complete(False)  # caller flow then escalates to a human (Blueprint section 10.1)
        # otherwise: stay in the task; the LLM naturally re-prompts