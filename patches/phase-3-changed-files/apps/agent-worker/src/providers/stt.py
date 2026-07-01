"""STT builder: Deepgram primary + Azure fallback via stt.FallbackAdapter (DR-0).

Streaming is required by FallbackAdapter; both providers stream. Arabic routes to Deepgram
language="ar" (the dedicated monolingual model), never "multi".
"""
from __future__ import annotations

from livekit.agents import stt as stt_module
from livekit.plugins import azure, deepgram

from providers._resilience import chaos_model


def build_stt(preset: dict[str, str], model: str = "nova-3", break_primary: bool = False):
    """Return a streaming STT FallbackAdapter for the given language preset."""
    primary = deepgram.STT(
        model=chaos_model(model, break_primary),
        language=preset["deepgram_language"],
    )
    fallback = azure.STT(language=preset["azure_stt_locale"])
    return stt_module.FallbackAdapter([primary, fallback])