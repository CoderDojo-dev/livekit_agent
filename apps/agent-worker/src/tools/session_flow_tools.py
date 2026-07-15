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
from contextlib import suppress

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



def _wrapped_providers(adapter, attr):
    """Concrete providers behind a FallbackAdapter (STT/TTS), or [adapter] itself."""
    instances = getattr(adapter, attr, None)
    if instances:
        return list(instances)
    return [adapter] if adapter is not None else []


def _update_stt_language(session, preset) -> None:
    """Best-effort: re-point every live STT provider at the new language."""
    for stt in _wrapped_providers(getattr(session, "stt", None), "_stt_instances"):
        upd = getattr(stt, "update_options", None)
        if callable(upd):
            with suppress(Exception):
                upd(language=preset["deepgram_language"])


def _update_tts_language(session, preset) -> None:
    """Best-effort: re-point every live TTS provider at the new language + voice."""
    for tts in _wrapped_providers(getattr(session, "tts", None), "_tts_instances"):
        upd = getattr(tts, "update_options", None)
        if not callable(upd):
            continue
        try:
            upd(language=preset["tts_iso"], voice=preset["cartesia_voice_id"])
        except TypeError:
            with suppress(Exception):
                upd(language=preset["tts_iso"])
        except Exception:
            pass


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


@function_tool()
async def switch_spoken_language(context: RunContext, new_language: str) -> dict:
    """Switch the spoken language of the call (STT, TTS, agent instructions, and user data) on the fly."""
    _MAP = {"fr": "French", "ar": "Arabic", "en": "English"}
    norm = new_language.lower().strip()[:2] if isinstance(new_language, str) else "fr"
    if norm not in _MAP:
        return {
            "outcome": "refused",
            "reason": "unsupported_language",
            "message": f"Politely explain that only French, Arabic, and English are supported ({new_language} requested).",
        }

    session = context.session
    user_data = getattr(session, "userdata", None)
    old_lang = getattr(user_data, "language", "fr") if user_data else "fr"
    old_val = getattr(old_lang, "value", old_lang)
    if str(old_val).lower().strip()[:2] == norm:
        return {
            "outcome": "already_active",
            "language": norm,
            "message": f"Politely acknowledge that we are already speaking in {_MAP[norm]}.",
        }

    if user_data is not None:
        setattr(user_data, "language", norm)

    # Hot-swap the LIVE pipeline. session.stt/.tts are READ-ONLY FallbackAdapters
    # in livekit-agents 1.6.3 (assigning to them raises AttributeError), so reach
    # the wrapped concrete providers and update their language in place via the
    # supported update_options() API (Deepgram STT + Cartesia TTS).
    from config.language_presets import LANGUAGE_PRESETS

    preset = LANGUAGE_PRESETS.get(norm, LANGUAGE_PRESETS["fr"])
    _update_stt_language(session, preset)
    _update_tts_language(session, preset)

    agent = getattr(session, "current_agent", None)
    if agent is not None:
        setattr(agent, "_language", norm)
        setattr(agent, "_lang_name", _MAP[norm])
        # Re-point the system instructions via the SUPPORTED async API. The old
        # chat_ctx.messages[0].content mutation was a guaranteed no-op:
        # ChatContext.messages is a read-only computed list and ChatMessage.content
        # is a list (not a str), so the `isinstance(content, str)` guard never passed.
        try:
            current = getattr(agent, "instructions", "") or ""
            if isinstance(current, str) and current:
                for _code, name in _MAP.items():
                    current = current.replace(name, _MAP[norm])
                await agent.update_instructions(current)
        except Exception as exc:
            logger.debug("instruction language update skipped: %s", exc)

    logger.info("switched spoken language mid-call from %s to %s", old_val, norm)
    return {
        "outcome": "executed",
        "language": norm,
        "message": f"Acknowledge in {_MAP[norm]} that we have switched languages to {_MAP[norm]}, and ask how you can help.",
    }
