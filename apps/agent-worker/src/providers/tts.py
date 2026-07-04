"""TTS builder: ElevenLabs primary + Cartesia optional fallback + Azure final fallback.

Provider chain:
  1. elevenlabs.TTS — primary (ELEVEN_API_KEY required)
  2. cartesia.TTS   — optional fallback (skipped when CARTESIA_API_KEY absent)
  3. azure.TTS      — final fallback (skipped when AZURE_SPEECH_KEY absent)

NOTE on Deepgram TTS:
  The installed LiveKit plugin bundle (livekit-agents[deepgram,...]==1.6.3) includes
  livekit-plugins-deepgram which currently exposes only STT functionality (deepgram.STT).
  Deepgram's Aura TTS product is available via their REST API but is NOT yet surfaced as
  a tts.TTS-compatible object in this version of the plugin. Therefore:
    - Deepgram is used as STT primary (see stt.py).
    - ElevenLabs remains TTS primary (uses ELEVEN_API_KEY).
    - Cartesia is wired as the first TTS fallback if CARTESIA_API_KEY is set.
    - Azure is the final TTS fallback if AZURE_SPEECH_KEY is set.
  When a future livekit-plugins-deepgram release adds deepgram.TTS, add it here as primary
  and demote ElevenLabs to first fallback.

ElevenLabs reads ELEVEN_API_KEY from the environment; language is ISO-639-1 (fr/ar/en).
"""
from __future__ import annotations

import os

from livekit.agents import tts as tts_module
from livekit.plugins import azure, cartesia, elevenlabs

from providers._resilience import chaos_model


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Return a TTS FallbackAdapter for the given language preset.

    Args:
        preset:        Language preset dict from LANGUAGE_PRESETS (must contain
                       tts_iso, azure_tts_voice, cartesia_voice_id).
        model:         ElevenLabs model ID (env: TTS_MODEL).
        voice_id:      ElevenLabs voice ID (env: ELEVEN_VOICE_ID).
        break_primary: Chaos toggle — forces primary failure for resilience tests.
    """
    # --- Primary: ElevenLabs ---
    primary = elevenlabs.TTS(
        model=chaos_model(model, break_primary),
        voice_id=voice_id,
        language=preset["tts_iso"],
    )

    providers: list = [primary]

    # --- Optional fallback: Cartesia (skipped if no key) ---
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    if cartesia_key:
        providers.append(
            cartesia.TTS(
                model=os.getenv("CARTESIA_TTS_MODEL", "sonic-2"),
                voice=preset["cartesia_voice_id"],
                api_key=cartesia_key,
            )
        )

    # --- Final fallback: Azure (skipped if no key) ---
    azure_key = os.getenv("AZURE_SPEECH_KEY", "")
    if azure_key:
        providers.append(azure.TTS(voice=preset["azure_tts_voice"]))

    return tts_module.FallbackAdapter(providers)