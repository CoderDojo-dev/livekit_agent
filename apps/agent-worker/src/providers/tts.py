"""4-layer TTS chain: Cartesia sonic-3 primary + ElevenLabs + Azure + GeminiTTS.

Provider chain (highest-priority first):
  1. cartesia.TTS  — Sonic 3           [primary, CARTESIA_API_KEY required]
  2. elevenlabs.TTS — ElevenLabs        [fallback, skipped if ELEVEN_API_KEY absent]
  3. azure.TTS      — Azure Cognitive   [fallback, skipped if AZURE_SPEECH_KEY absent]
  4. google.beta.GeminiTTS — GeminiTTS  [fallback, skipped if GOOGLE_API_KEY absent]

Design:
  - cartesia.TTS receives language= so the model emits properly-accented phonemes.
  - ElevenLabs must NOT receive language= (plugin 1.6.3 raises TypeError).
  - GeminiTTS is the final layer — it is the cheapest and lasts the longest.
"""
from __future__ import annotations

import logging

from livekit.agents import tts as tts_module
from livekit.plugins import azure, cartesia, elevenlabs, google

from config.settings import Settings

logger = logging.getLogger(__name__)


def build_tts(settings: Settings) -> tts_module.TTSFallbackAdapter:
    """Return a 4-layer TTS FallbackAdapter with Cartesia sonic-3 as primary.

    Every provider except Cartesia is key-gated — if its key is absent
    the layer is silently skipped.
    """
    cartesia_key = settings.cartesia_api_key
    if not cartesia_key:
        logger.warning("CARTESIA_API_KEY is empty — TTS chain has no primary!")

    primary = cartesia.TTS(
        model=settings.cartesia_tts_model,
        api_key=cartesia_key,
        language=settings.session_language,
    )

    providers: list = [primary]

    eleven_key = settings.eleven_api_key
    if eleven_key:
        providers.append(elevenlabs.TTS(api_key=eleven_key))

    azure_key = settings.azure_speech_key
    if azure_key:
        providers.append(azure.TTS(speech_key=azure_key))

    gemini_key = settings.google_api_key
    if gemini_key:
        providers.append(
            google.beta.GeminiTTS(
                model=settings.gemini_tts_model,
                voice=settings.gemini_tts_voice,
            )
        )

    return tts_module.TTSFallbackAdapter(providers, attempt_timeout=12.0)
