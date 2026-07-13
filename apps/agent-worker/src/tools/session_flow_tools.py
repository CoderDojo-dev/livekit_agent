"""Agent-initiated graceful end of the conversation (Decision -> Execution close).

Deterministic close: speak a bounded, in-language farewell to completion, then
delete the LiveKit room. Deleting the room disconnects the caller, which drives
the frontend through the EXACT same reactive cleanup as the manual "End Call"
button (connectionState -> "disconnected"); there is no parallel teardown path.
The job's existing shutdown callbacks then finalize the durable conversation
record and metrics.

The "confirm there is nothing else, then thank + say goodbye" conversational
protocol lives in the shared instructions (see agents.base_agent.CLOSING_PROTOCOL);
this tool is the deterministic execution the LLM calls once that protocol is
satisfied.
"""
from __future__ import annotations

import logging

from livekit import api
from livekit.agents import RunContext, function_tool, get_job_context
from livekit.agents.llm.tool_context import StopResponse

from tools.voice_flow import say_and_wait

logger = logging.getLogger(__name__)

# Fixed, bounded farewell (thanks + goodbye) per supported language. A fixed line
# keeps the close deterministic and race-free versus generating another LLM turn
# while the room is being torn down. The LLM handles the "anything else?"
# confirmation BEFORE calling this tool.
_FAREWELLS = {
    "fr": "Merci de votre appel. Je vous souhaite une excellente journée. Au revoir !",
    "ar": "شكرًا لاتصالكم. أتمنى لكم يومًا سعيدًا. مع السلامة!",
    "en": "Thank you for calling. Have a wonderful day. Goodbye!",
}


def _language_code(user_data) -> str:
    """Best-effort 2-letter language code from session user-data (defaults to fr)."""
    language = getattr(user_data, "language", None)
    value = getattr(language, "value", language)  # tolerate enum or str
    code = str(value or "fr").lower()[:2]
    return code if code in _FAREWELLS else "fr"


@function_tool()
async def end_conversation(context: RunContext) -> None:
    """Close the call gracefully once the caller confirms they need nothing else.

    Call this only after the caller clearly has no further requests (or clearly
    wants to leave / says goodbye). It delivers a short spoken farewell and then
    ends the session. Never call it while the caller still needs help.
    """
    session = context.session
    user_data = getattr(session, "userdata", None)

    # Idempotent: a duplicate emission must not run teardown twice.
    if user_data is not None and getattr(user_data, "conversation_ending", False):
        raise StopResponse()
    if user_data is not None:
        user_data.conversation_ending = True

    farewell = _FAREWELLS[_language_code(user_data)]

    # Speak the farewell to completion (non-interruptible) BEFORE closing so the
    # caller actually hears it. say_and_wait bounds playback so a TTS/playout
    # failure can never hold the line open.
    try:
        await say_and_wait(session, farewell, allow_interruptions=False)
    except Exception as exc:
        logger.warning("farewell speech skipped: %s", exc)

    # Delete the room -> caller disconnects -> the frontend runs the identical
    # cleanup as the manual End Call button. Job shutdown callbacks finalize the
    # conversation record. Guarded so a close failure is logged, never raised
    # into the voice path.
    try:
        job = get_job_context()
        await job.api.room.delete_room(api.DeleteRoomRequest(room=job.room.name))
        logger.info("end_conversation: room '%s' deleted, closing session", job.room.name)
    except Exception as exc:
        logger.error("end_conversation: room delete failed: %s", exc)

    # No trailing LLM/TTS turn after the farewell.
    raise StopResponse()
