"""Per-language presets that the providers layer mirrors from DR-0 (Phase 0).

Each language entry must supply ALL keys consumed by the STT and TTS builders:
  - deepgram_language  → deepgram.STT(language=...)
  - azure_stt_locale   → azure.STT(language=...)        [fallback]
  - gladia_language    → gladia.STT(language=...)        [optional fallback]
  - tts_iso            → elevenlabs.TTS(language=...)    [TTS primary]
  - azure_tts_voice    → azure.TTS(voice=...)            [TTS fallback]
  - cartesia_voice_id  → cartesia.TTS(voice=...)         [optional TTS provider]

Arabic: Deepgram uses language="ar" (single-language model, never "multi"). See stt.py.
"""
from __future__ import annotations

# Decided in Phase 0 (docs/architecture/phase-0-verification-gate/00-DECISION-RECORD.md).
LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
    "fr": {
        # STT — Deepgram primary
        "deepgram_language": "fr",
        # STT — Azure fallback
        "azure_stt_locale": "fr-FR",
        # STT — Gladia (optional fallback, BCP-47 locale)
        "gladia_language": "fr",
        # TTS — ElevenLabs primary (ISO-639-1)
        "tts_iso": "fr",
        # TTS — Azure fallback (Neural voice name)
        "azure_tts_voice": "fr-FR-DeniseNeural",
        # TTS — Cartesia voice ID (UUID, fr-FR female voice)
        "cartesia_voice_id": "22f1a356-56c2-4428-bc91-2ab2e6d0c215",
    },
    "ar": {
        # STT — Deepgram primary (language="ar", single-language model — never "multi")
        "deepgram_language": "ar",
        # STT — Azure fallback
        "azure_stt_locale": "ar-EG",
        # STT — Gladia
        "gladia_language": "ar",
        # TTS — ElevenLabs primary
        "tts_iso": "ar",
        # TTS — Azure fallback
        "azure_tts_voice": "ar-EG-SalmaNeural",
        # TTS — Cartesia voice ID (UUID, Arabic voice)
        "cartesia_voice_id": "79743797-2087-422f-8e74-6d2b03ae5b31",
    },
    "en": {
        # STT — Deepgram primary
        "deepgram_language": "en",
        # STT — Azure fallback
        "azure_stt_locale": "en-US",
        # STT — Gladia
        "gladia_language": "en",
        # TTS — ElevenLabs primary
        "tts_iso": "en",
        # TTS — Azure fallback
        "azure_tts_voice": "en-US-JennyNeural",
        # TTS — Cartesia voice ID (UUID, en-US female voice)
        "cartesia_voice_id": "694f9389-aac1-45b6-b726-9d9369183238",
    },
}

GREETINGS: dict[str, str] = {
    "fr": "Saluez brièvement l'appelant en français et demandez comment vous pouvez l'aider aujourd'hui.",
    "ar": "حي المتصل باختصار باللغة العربية واسأله كيف يمكنك مساعدته اليوم.",
    "en": "Briefly greet the caller in English and ask how you can help today.",
}
