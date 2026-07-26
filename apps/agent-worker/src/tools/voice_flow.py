"""Interruption-safe primitives for tool speech and agent handoffs.

Tool-only LLM turns can produce an empty text stream. Speaking explicitly avoids
passing that empty stream into TTS. Every explicit speech is also bounded so a
provider or playback failure cannot hold the session forever.
"""
from __future__ import annotations

import asyncio
from typing import Any

from livekit.agents.types import NotGivenOr

from livekit.agents import RunContext
from livekit.agents.llm.tool_context import StopResponse

DEFAULT_SPEECH_TIMEOUT_S = 20.0


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
    timeout_s: float = DEFAULT_SPEECH_TIMEOUT_S,
) -> Any:
    """Play a short transition completely, then return the next Agent to LiveKit."""
    await say_and_wait(
        context.session,
        message,
        allow_interruptions=False,
        timeout_s=timeout_s,
    )
    return next_agent


def persona_tts(tts: NotGivenOr[object] | None) -> object | None:
    """Normalise a NotGivenOr TTS value so callers can pass it to AgentTask safely."""
    if tts is None or isinstance(tts, NotGivenOr):
        return None
    return tts


def active_persona_tts(context: RunContext | None) -> object | None:
    """Borrow the currently active persona's TTS identity for a bounded sub-flow.

    When the BillingAgent runs IdentityVerificationTask, for example, the CIN
    prompt should be spoken in the *billing* voice, not the session default
    TTS.  Returns None when no agent is active (safe fallback to session voice).
    """
    if context is None:
        return None
    current = getattr(context.session, "current_agent", None)
    tts = getattr(current, "tts", None)
    return persona_tts(tts)
