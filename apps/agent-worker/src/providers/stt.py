"""STT builder: Deepgram primary + Gladia optional fallback + Azure final fallback.

Provider chain:
  1. deepgram.STT  — primary (DEEPGRAM_API_KEY required)
  2. gladia.STT    — optional fallback (skipped when GLADIA_API_KEY absent)
  3. azure.STT     — final fallback (skipped when AZURE_SPEECH_KEY absent)

Streaming is required by FallbackAdapter; all three providers stream.
Arabic routes to Deepgram language="ar" (the dedicated monolingual model), never "multi".
"""
from __future__ import annotations

import inspect
import logging
import os

from livekit.agents import stt as stt_module
from livekit.plugins import azure, deepgram, gladia  # type: ignore[attr-defined]

from providers._resilience import chaos_model

logger = logging.getLogger(__name__)


def build_stt(preset: dict[str, str], model: str = "nova-3", break_primary: bool = False, keyterms: list[str] | None = None):
    """Return a streaming STT FallbackAdapter for the given language preset.

    Args:
        preset:        Language preset dict from LANGUAGE_PRESETS (must contain
                       deepgram_language, azure_stt_locale, gladia_language).
        model:         Deepgram model ID (env: STT_MODEL, default: nova-3).
        break_primary: Chaos toggle — forces primary failure for resilience tests.
        keyterms:      Optional place names / keyterms to announce to Deepgram.
    """
    # --- Primary: Deepgram ---
    primary_kwargs: dict = {
        "model": chaos_model(model, break_primary),
        "language": preset["deepgram_language"],
    }
    if keyterms:
        # Le parametre s'appelle "keyterms" dans le plugin Deepgram. Si la version
        # installee ne le connait pas, on n'envoie rien plutot que de casser l'appel.
        if "keyterms" in inspect.signature(deepgram.STT.__init__).parameters:
            primary_kwargs["keyterms"] = list(keyterms)
        else:
            logger.warning(
                "livekit-plugins-deepgram sans parametre 'keyterms' : "
                "%d noms de lieux non transmis",
                len(keyterms),
            )
    primary = deepgram.STT(**primary_kwargs)

    providers: list = [primary]

    # --- Optional fallback: Gladia (skipped if no key) ---
    gladia_key = os.getenv("GLADIA_API_KEY", "")
    if gladia_key:
        providers.append(
            gladia.STT(
                languages=[preset["gladia_language"]],
                api_key=gladia_key,
            )
        )

    # --- Final fallback: Azure (skipped if no key) ---
    azure_key = os.getenv("AZURE_SPEECH_KEY", "")
    if azure_key:
        providers.append(azure.STT(language=preset["azure_stt_locale"]))

    return stt_module.FallbackAdapter(providers)