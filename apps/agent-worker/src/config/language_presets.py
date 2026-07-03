"""Per-language presets that the providers layer mirrors from DR-0 (Phase 0)."""
from __future__ import annotations

# Decided in Phase 0 (docs/architecture/phase-0-verification-gate/00-DECISION-RECORD.md).
LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
    "fr": {"stt_language": "fr", "tts_voice": "fr"},
    "ar": {"stt_language": "ar", "tts_voice": "ar"},  # Arabic uses language=ar, never 'multi'
    "en": {"stt_language": "en", "tts_voice": "en"},
}

GREETINGS: dict[str, str] = {
    "fr": "Saluez brièvement l'appelant en français et demandez comment vous pouvez l'aider aujourd'hui.",
    "ar": "حي المتصل باختصار باللغة العربية واسأله كيف يمكنك مساعدته اليوم.",
    "en": "Briefly greet the caller in English and ask how you can help today.",
}
