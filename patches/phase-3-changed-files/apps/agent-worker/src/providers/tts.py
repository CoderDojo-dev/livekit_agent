"""TTS builder: ElevenLabs Flash v2.5 primary + Azure Neural fallback via tts.FallbackAdapter.

ElevenLabs reads ELEVEN_API_KEY from the environment; language is ISO-639-1 (fr/ar/en).
"""
from __future__ import annotations

from livekit.agents import tts as tts_module
from livekit.plugins import azure, elevenlabs

from providers._resilience import chaos_model


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Return a TTS FallbackAdapter for the given language preset."""
    primary = elevenlabs.TTS(
        model=chaos_model(model, break_primary),
        voice_id=voice_id,
        language=preset["tts_iso"],
    )
    fallback = azure.TTS(voice=preset["azure_tts_voice"])
    return tts_module.FallbackAdapter([primary, fallback])