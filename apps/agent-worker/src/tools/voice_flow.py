"""Interruption-safe primitives for tool speech and agent handoffs.

Tool-only LLM turns can produce an empty text stream. Speaking explicitly avoids
passing that empty stream into TTS. Every explicit speech is also bounded so a
provider or playback failure cannot hold the session forever.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from livekit.agents.types import NOT_GIVEN, NotGiven, NotGivenOr

from livekit.agents import RunContext
from livekit.agents.llm.tool_context import StopResponse

logger = logging.getLogger(__name__)

DEFAULT_SPEECH_TIMEOUT_S = 20.0

MAX_HANDOFFS_PER_CALL = 4

_HANDOFF_REFUSAL = {
    "fr": "Vous avez déjà été transféré plusieurs fois. Je dois clôturer cet appel, "
    "mais je reste disponible pour toute autre question. Bonne journée.",
    "ar": "تم تحويلك عدة مرات. يجب أن أنهي هذه المكالمة الآن، لكنني أبقى في خدمتك "
    "لأي سؤال آخر. يوم سعيد.",
    "en": "You have already been transferred several times. I need to end this call, "
    "but I remain available for any other question. Have a good day.",
}


def _handoff_refusal_reason(session_state: Any) -> str | None:
    """Return a reason when the caller may not be handed off again, else ``None``."""
    handoff_count = getattr(session_state, "handoff_count", 0)
    if handoff_count >= MAX_HANDOFFS_PER_CALL:
        return f"handoff refused by loop guard: count={handoff_count} >= {MAX_HANDOFFS_PER_CALL}"
    last_handoff_turn = getattr(session_state, "last_handoff_turn", -1)
    caller_turn_index = getattr(session_state, "caller_turn_index", 0)
    if last_handoff_turn == caller_turn_index:
        return (
            "handoff refused by loop guard: already handed off on caller turn "
            f"{caller_turn_index}"
        )
    return None


def _record_handoff(session_state: Any, agent_name: str) -> None:
    """Record one handoff on the session state, ignoring callers that lack one."""
    if session_state is None:
        return
    setattr(session_state, "handoff_count", getattr(session_state, "handoff_count", 0) + 1)
    setattr(session_state, "last_handoff_turn", getattr(session_state, "caller_turn_index", 0))


def current_chat_ctx(context: RunContext) -> Any | None:
    """Return the current agent chat context so handoffs preserve conversation history."""
    current_agent = getattr(context.session, "current_agent", None)
    return getattr(current_agent, "chat_ctx", None)


def _interrupt_speech(speech: Any) -> None:
    """Best-effort cleanup compatible with current and older SpeechHandle signatures."""
    interrupt = getattr(speech, "interrupt", None)
    if not callable(interrupt):
        return

    try:
        interrupt(force=True)
    except TypeError:
        interrupt()
    except Exception:
        pass


async def say_and_wait(
    session: Any,
    text: str,
    *,
    allow_interruptions: bool,
    timeout_s: float = DEFAULT_SPEECH_TIMEOUT_S,
) -> Any:
    """Speak, await completion/interruption, and bound the playback lifecycle."""
    message = (text or "").strip()
    if not message:
        raise ValueError("refusing to create an empty speech stream")

    speech = session.say(message, allow_interruptions=allow_interruptions)
    speech_task = asyncio.ensure_future(speech)

    try:
        await asyncio.wait_for(asyncio.shield(speech_task), timeout=timeout_s)
    except BaseException:
        _interrupt_speech(speech)
        await asyncio.gather(speech_task, return_exceptions=True)
        raise

    return speech


async def say_and_stop(
    context: RunContext,
    text: str,
    *,
    timeout_s: float = DEFAULT_SPEECH_TIMEOUT_S,
) -> None:
    """Speak a tool's complete response and prevent a redundant empty LLM/TTS turn."""
    await say_and_wait(
        context.session,
        text,
        allow_interruptions=True,
        timeout_s=timeout_s,
    )
    raise StopResponse()


async def handoff_with_message(
    context: RunContext,
    next_agent: Any,
    message: str,
    *,
    language: str = "fr",
    loop_guard: bool = True,
    timeout_s: float = DEFAULT_SPEECH_TIMEOUT_S,
) -> Any:
    """Play a short transition completely, then return the next Agent to LiveKit.

    ``loop_guard`` refuses another handoff once ``MAX_HANDOFFS_PER_CALL`` have
    already been recorded on the session state, ending the call politely instead
    of letting the caller bounce between agents forever.
    """
    if loop_guard:
        session_state = getattr(context.session, "userdata", None)
        reason = _handoff_refusal_reason(session_state)
        if reason is not None:
            logger.warning(reason)
            await say_and_stop(
                context,
                _HANDOFF_REFUSAL.get(language, _HANDOFF_REFUSAL["fr"]),
                timeout_s=timeout_s,
            )
            return None
    await say_and_wait(
        context.session,
        message,
        allow_interruptions=False,
        timeout_s=timeout_s,
    )
    if loop_guard:
        session_state = getattr(context.session, "userdata", None)
        current_agent = getattr(context.session, "current_agent", None)
        _record_handoff(session_state, getattr(current_agent, "name", "unknown"))
    return next_agent


def persona_tts(tts: NotGivenOr[object] | None) -> object:
    """Normalise a persona TTS value so a bounded sub-flow can inherit it safely.

    Returns a real TTS when one is set, otherwise NOT_GIVEN. It must NEVER return
    ``None``: LiveKit resolves an activity's TTS as
    ``agent.tts if is_given(agent.tts) else session.tts`` and ``is_given(None)`` is
    True, so ``tts=None`` means "this agent has NO TTS" and raises
    "tts_node called but no TTS node is available". ``NOT_GIVEN`` is the sentinel
    meaning "unspecified -> use the session TTS". We test the ``NotGiven`` *class*
    (isinstance-safe); ``NotGivenOr`` is a Union alias and ``isinstance`` on it raises.
    """
    if tts is None or isinstance(tts, NotGiven):
        return NOT_GIVEN
    return tts


def active_persona_tts(context: RunContext | None) -> object:
    """Borrow the currently active persona's TTS for a bounded sub-flow.

    When the BillingAgent runs IdentityVerificationTask, for example, the CIN
    prompt is spoken in the *billing* voice, not the session default. Returns
    ``NOT_GIVEN`` (never ``None``) when no agent/context is available, so the
    sub-flow falls back to the session voice instead of being muted.
    """
    if context is None:
        return NOT_GIVEN
    current = getattr(context.session, "current_agent", None)
    return persona_tts(getattr(current, "tts", NOT_GIVEN))
