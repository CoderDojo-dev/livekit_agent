"""Recording-consent task (CDC section 8.1). Runs at TriageAgent.on_enter before business talk.

Now implemented (review note 6): asks for explicit consent in the caller's language and
records the boolean in session user-data. The audit/consent-event persistence lands with the
notification/compliance work; the decision itself is captured here from call start.
"""
from __future__ import annotations

from livekit.agents import AgentTask, function_tool


class ConsentTask(AgentTask[bool]):
    """Takes over the session briefly to capture recording consent, then returns the boolean."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Before anything else, ask the caller - briefly and in their language - for "
                "consent to record the call for quality and security purposes. Wait for a clear "
                "yes or no, then record it. Do not start solving their request yet."
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        """Prompt for recording consent."""
        await self.session.generate_reply(
            instructions="Ask the caller, briefly and in their language, for consent to record the call.",
        )

    @function_tool()
    async def record_consent(self, granted: bool) -> None:
        """Record whether the caller granted consent to record the call (durable + audited)."""
        user_data = self.session.userdata
        user_data.recording_consent = granted
        writer = getattr(user_data, "conversation_writer", None)
        if writer is not None:
            customer = getattr(user_data, "customer_context", None)
            writer.record_consent(
                granted=granted,
                language=getattr(user_data, "language", None),
                customer_id=customer.customer_id if customer else None,
            )
        self.complete(granted)