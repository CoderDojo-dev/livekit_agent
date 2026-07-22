"""TTS builder: FallbackAdapter multi-providers (français d'abord, Azure supprimé).

Providers temps réel (tous streaming, tous FR). Chaque provider n'est inclus que si sa
clé est présente (les providers non configurés sont ignorés silencieusement) :
  - elevenlabs.TTS  (ELEVEN_API_KEY)    — naturel premium
  - cartesia.TTS    (CARTESIA_API_KEY)  — latence ultra-basse  [primary par défaut]
  - inworld.TTS     (INWORLD_API_KEY)   — expressif, FR GA (clé Base64)
  - smallestai.TTS  (SMALLEST_API_KEY)  — le plus rapide, FR (Beta)

Le primary est choisi à l'exécution via TTS_PRIMARY (défaut "cartesia") ; les autres
suivent en fallback dans un ordre qualité fixe. Le chaos (CHAOS_BREAK_TTS) ne casse que
le primary sélectionné, pour exercer le vrai chemin de fallback. Si aucune clé n'est
configurée, on lève une erreur (le worker échoue au démarrage plutôt que de rester muet).

Azure TTS supprimé (pas de compte/crédits) ; Azure reste STT-only (voir stt.py).
Gemini TTS volontairement NON branché : google.beta.GeminiTTS est beta avec
streaming=False (bufferise tout l'énoncé -> latence élevée), inadapté à une chaîne
temps réel. Placeholders conservés dans .env.example pour une future version streaming.
"""

from __future__ import annotations

import logging
import os

from livekit.agents import tts as tts_module
from livekit.plugins import (
    cartesia,
    elevenlabs,
    inworld,
    smallestai,
)

from providers._resilience import chaos_model

logger = logging.getLogger(__name__)

# Ordre qualité (le plus naturel/pro d'abord). Le primary runtime est déplacé en tête ;
# les autres gardent cet ordre relatif comme fallbacks.
_QUALITY_ORDER = ("elevenlabs", "cartesia", "inworld", "smallestai")
_DEFAULT_PRIMARY = "cartesia"


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Retourne un FallbackAdapter TTS pour le preset de langue donné.

    Args:
        preset:        preset de LANGUAGE_PRESETS (doit contenir tts_iso,
                       cartesia_voice_id, inworld_language).
        model:         modèle ElevenLabs (env: TTS_MODEL).
        voice_id:      voix ElevenLabs (env: ELEVEN_VOICE_ID).
        break_primary: chaos — force UNIQUEMENT le primary sélectionné à échouer.
    """

    def _elevenlabs(chaos: bool):
        if not os.getenv("ELEVEN_API_KEY", ""):
            return None
        return elevenlabs.TTS(
            model=chaos_model(model, chaos),
            voice_id=voice_id,
            language=preset["tts_iso"],
        )

    def _cartesia(chaos: bool):
        key = os.getenv("CARTESIA_API_KEY", "")
        if not key:
            return None
        return cartesia.TTS(
            model=chaos_model(os.getenv("CARTESIA_TTS_MODEL", "sonic-3"), chaos),
            voice=preset["cartesia_voice_id"],
            language=preset["tts_iso"],
            api_key=key,
        )

    def _inworld(chaos: bool):
        if not os.getenv("INWORLD_API_KEY", ""):
            return None
        return inworld.TTS(
            model=chaos_model(os.getenv("INWORLD_TTS_MODEL", "inworld-tts-2"), chaos),
            voice=os.getenv("INWORLD_VOICE_ID", "alain"),
            language=preset["inworld_language"],  # BCP-47, ex: fr-FR
        )

    def _smallestai(chaos: bool):
        if not os.getenv("SMALLEST_API_KEY", ""):
            return None
        # Smallest.ai n'a AUCUNE voix arabe -> on l'exclut proprement pour ar.
        if preset["tts_iso"] == "ar":
            return None
        return smallestai.TTS(
            model=chaos_model(os.getenv("SMALLEST_TTS_MODEL", "lightning_v3.1"), chaos),
            voice_id=os.getenv("SMALLEST_VOICE_ID", "juliette"),
            language=preset["tts_iso"],
            sample_rate=24000,
        )

    factories = {
        "elevenlabs": _elevenlabs,
        "cartesia": _cartesia,
        "inworld": _inworld,
        "smallestai": _smallestai,
    }

    primary = os.getenv("TTS_PRIMARY", _DEFAULT_PRIMARY).strip().lower()
    if primary not in factories:
        logger.warning("TTS_PRIMARY=%r inconnu, repli sur %r", primary, _DEFAULT_PRIMARY)
        primary = _DEFAULT_PRIMARY
    order = [primary] + [name for name in _QUALITY_ORDER if name != primary]

    providers: list = []
    active: list[str] = []
    for index, name in enumerate(order):
        tts_obj = factories[name](break_primary and index == 0)
        if tts_obj is not None:
            providers.append(tts_obj)
            active.append(name)

    if not providers:
        raise RuntimeError(
            "Aucun provider TTS configuré. Définis au moins une de : "
            "ELEVEN_API_KEY, CARTESIA_API_KEY, INWORLD_API_KEY, SMALLEST_API_KEY."
        )

    logger.info("tts providers configured: %s (primary demandé=%s)", active, primary)
    return tts_module.FallbackAdapter(providers)
