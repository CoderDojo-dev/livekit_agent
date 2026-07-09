"""TTS builder: ElevenLabs primary + Cartesia fallback + Deepgram/Azure safety nets.

Provider chain, skipping providers whose keys/classes are unavailable:
  1. ElevenLabs TTS — primary when ELEVEN_API_KEY exists
  2. Cartesia TTS   — fallback when CARTESIA_API_KEY exists
  3. Deepgram Aura  — emergency safety net when DEEPGRAM_API_KEY and deepgram.TTS exist
  4. Azure TTS      — final fallback when AZURE_SPEECH_KEY exists

Deepgram Aura voices are English-only in common configs. Not ideal for FR/AR,
but rough audio is better than total silence when Cartesia stalls.
"""
from __future__ import annotations

import logging
import os

from livekit.agents import tts as tts_module
from livekit.plugins import azure, cartesia, deepgram, elevenlabs

from providers._resilience import chaos_model

logger = logging.getLogger(__name__)


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Return a TTS FallbackAdapter for the given language preset."""
    providers: list = []

    # --- Primary: ElevenLabs ---
    eleven_key = os.getenv("ELEVEN_API_KEY", "")
    if eleven_key:
        providers.append(
            elevenlabs.TTS(
                model=chaos_model(model, break_primary),
                voice_id=voice_id,
                language=preset["tts_iso"],
            )
        )

    # --- Fallback: Cartesia ---
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    if cartesia_key:
        providers.append(
            cartesia.TTS(
                model=os.getenv("CARTESIA_TTS_MODEL", "sonic-3"),
                voice=preset["cartesia_voice_id"],
                language=preset["tts_iso"],
                api_key=cartesia_key,
            )
        )

    # --- Emergency safety net: Deepgram Aura ---
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    if deepgram_key and hasattr(deepgram, "TTS"):
        try:
            providers.append(
                deepgram.TTS(
                    model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"),
                    api_key=deepgram_key,
                )
            )
        except TypeError:
            # Some plugin versions read the key from env and do not accept api_key.
            providers.append(
                deepgram.TTS(model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"))
            )

    # --- Final fallback: Azure ---
    azure_key = os.getenv("AZURE_SPEECH_KEY", "")
    if azure_key:
        providers.append(
            azure.TTS(
                speech_key=azure_key,
                speech_region=os.getenv("AZURE_SPEECH_REGION", "francecentral"),
                voice=preset["azure_tts_voice"],
            )
        )

    if not providers:
        raise RuntimeError(
            "No TTS provider configured: set ELEVEN_API_KEY, CARTESIA_API_KEY, DEEPGRAM_API_KEY or AZURE_SPEECH_KEY"
        )

    logger.info("tts providers configured: %s", [type(p).__name__ for p in providers])
    return tts_module.FallbackAdapter(providers)
