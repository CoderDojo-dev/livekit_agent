"""Phase-0 provider routing matrix — the machine-readable form of DR-0.

Responsibility: encode the *decided* per-language STT/TTS/turn-detector/LLM routing
and the *verified* language-support facts (with sources) as pure data, so the decision
is testable offline and the Phase-1 ``providers/`` wiring has one source to mirror.

This module imports no LiveKit/vendor SDK and performs no I/O. It is documentation
evidence under ``docs/architecture/``, not a production module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Supported scope (CDC §2.4 / Blueprint ADR §5.7) ------------------------------------

SUPPORTED_LANGUAGES: tuple[str, ...] = ("fr", "ar", "en")  # French primary, Arabic, English


# --- Value objects ----------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderChoice:
    """A single provider/model pick for one component and one language."""

    provider: str          # e.g. "deepgram", "elevenlabs", "azure", "openai", "google"
    model: str             # e.g. "nova-3", "eleven_flash_v2_5"
    params: dict[str, str] = field(default_factory=dict)  # e.g. {"language": "ar"}
    source: str = ""       # verification URL backing this pick


@dataclass(frozen=True)
class Chain:
    """A primary + ordered fallbacks chain (wired via FallbackAdapter in Phase 1)."""

    primary: ProviderChoice
    fallbacks: tuple[ProviderChoice, ...]

    def all_choices(self) -> tuple[ProviderChoice, ...]:
        return (self.primary, *self.fallbacks)


# --- Verified language support (each entry is doc-sourced; see DR-0 sections 1-2) --------
# provider -> component -> frozenset of language codes verified as supported.

VERIFIED_SUPPORT: dict[str, dict[str, frozenset[str]]] = {
    "deepgram": {
        # Nova-3 multilingual ("multi") covers fr/en but NOT ar; Arabic is a dedicated
        # monolingual model selected via language="ar".
        "stt": frozenset({"fr", "en", "ar"}),
    },
    "azure": {
        "stt": frozenset({"fr", "ar", "en"}),
        "tts": frozenset({"fr", "ar", "en"}),
    },
    "elevenlabs": {
        "tts": frozenset({"fr", "ar", "en"}),  # Flash v2.5 / Multilingual v2
    },
    "openai": {
        "llm": frozenset({"fr", "ar", "en"}),
    },
    "google": {
        "llm": frozenset({"fr", "ar", "en"}),
    },
}

# Audio-native turn detector verified languages (14 total; we only need these three).
TURN_DETECTOR_LANGUAGES: frozenset[str] = frozenset({"fr", "ar", "en"})

_SRC_DG_AR = "https://deepgram.com/learn/nova-3-arabic-speech-to-text-production-grade-stt"
_SRC_DG_ML = "https://deepgram.com/learn/nova-3-multilingual-major-wer-improvements-across-languages"
_SRC_AZ = "https://learn.microsoft.com/azure/ai-services/speech-service/language-support"
_SRC_11 = "https://elevenlabs.io/docs/overview/capabilities/text-to-speech"
_SRC_TD = "https://docs.livekit.io/agents/build/turns/turn-detector/"


# --- STT routing (streaming; FallbackAdapter requires streaming STT) ---------------------

STT_ROUTING: dict[str, Chain] = {
    "fr": Chain(
        primary=ProviderChoice("deepgram", "nova-3", {"language": "fr"}, _SRC_DG_ML),
        fallbacks=(ProviderChoice("azure", "default", {"language": "fr-FR"}, _SRC_AZ),),
    ),
    "en": Chain(
        primary=ProviderChoice("deepgram", "nova-3", {"language": "en"}, _SRC_DG_ML),
        fallbacks=(ProviderChoice("azure", "default", {"language": "en-US"}, _SRC_AZ),),
    ),
    "ar": Chain(
        # Dedicated Arabic monolingual model — NOT the "multi" set.
        primary=ProviderChoice("deepgram", "nova-3", {"language": "ar"}, _SRC_DG_AR),
        fallbacks=(ProviderChoice("azure", "default", {"language": "ar-SA"}, _SRC_AZ),),
    ),
}


# --- TTS routing -------------------------------------------------------------------------

TTS_ROUTING: dict[str, Chain] = {
    "fr": Chain(
        primary=ProviderChoice("elevenlabs", "eleven_flash_v2_5", {"language": "fr"}, _SRC_11),
        fallbacks=(ProviderChoice("azure", "fr-FR-DeniseNeural", {"language": "fr-FR"}, _SRC_AZ),),
    ),
    "en": Chain(
        primary=ProviderChoice("elevenlabs", "eleven_flash_v2_5", {"language": "en"}, _SRC_11),
        fallbacks=(ProviderChoice("azure", "en-US-AvaNeural", {"language": "en-US"}, _SRC_AZ),),
    ),
    "ar": Chain(
        # Primary AR voice confirmed by Phase-1 listening test; both are verified-supported.
        primary=ProviderChoice("elevenlabs", "eleven_flash_v2_5", {"language": "ar"}, _SRC_11),
        fallbacks=(ProviderChoice("azure", "ar-SA-HamedNeural", {"language": "ar-SA"}, _SRC_AZ),),
    ),
}


# --- LLM topology (provider+fallback; exact model-ids bound in Phase 1 [verify]) ---------

LLM_CHAIN: Chain = Chain(
    primary=ProviderChoice("openai", "gpt-4.1", {}, "https://docs.livekit.io/agents/models/"),
    fallbacks=(ProviderChoice("google", "gemini-2.x", {}, "https://docs.livekit.io/agents/models/"),),
)


# --- Turn detector + VAD (shared across languages) --------------------------------------

TURN_DETECTOR: ProviderChoice = ProviderChoice(
    provider="livekit",
    model="audio-eou (inference.TurnDetector)",
    params={"runtime": "local-cpu", "min_silence_s": "0.25"},
    source=_SRC_TD,
)
VAD: ProviderChoice = ProviderChoice("silero", "vad", {"min_silence_s": "0.25"}, _SRC_TD)


# --- Helpers ----------------------------------------------------------------------------

def is_supported(provider: str, component: str, language: str) -> bool:
    """Return True iff ``provider`` is doc-verified for ``component`` in ``language``."""
    return language in VERIFIED_SUPPORT.get(provider, {}).get(component, frozenset())
