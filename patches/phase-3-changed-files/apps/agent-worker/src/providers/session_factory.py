"""Thin session assembler (cookbook section 4/5, SRP-refined).

This file contains NO vendor-plugin import. It composes the per-concern builders from the
providers/ package into one AgentSession. Vendor coupling lives only in the builder modules
(stt/tts/llm/vad) and the isolated turn_detection wrapper — the providers/ package is the
single vendor boundary, enforceable by a lint rule: no `livekit.plugins` import may appear
outside apps/agent-worker/src/providers/.
"""
from __future__ import annotations

from livekit.agents import AgentSession

from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from providers.llm import build_llm
from providers.stt import build_stt
from providers.tts import build_tts
from providers.turn_detection import build_turn_detector
from providers.vad import build_vad


def build_agent_session(settings: Settings, language: str) -> AgentSession:
    """Assemble the STT/LLM/TTS/VAD/turn-detection pipeline for ``language`` (composition only).

    Each of STT/LLM/TTS is a FallbackAdapter([primary, secondary]) so a single provider
    outage never drops the call (Blueprint section 1).
    """
    preset = LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])
    return AgentSession(
        vad=build_vad(settings.vad_min_silence),
        turn_detection=build_turn_detector(),
        stt=build_stt(preset, settings.stt_model, settings.chaos_break_stt),
        llm=build_llm(settings.llm_primary_model, settings.llm_fallback_model, settings.chaos_break_llm),
        tts=build_tts(preset, settings.tts_model, settings.eleven_voice_id, settings.chaos_break_tts),
        preemptive_generation=settings.preemptive_generation,
    )