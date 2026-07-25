# Version 49 — Multi-TTS Provider Expansion (Inworld + Smallest.ai)

## What's new
- **New TTS providers**: Inworld.TTS (FR GA, Base64 key, BCP-47) + Smallest.ai.TTS (lightning_v3.1, FR Beta, sample_rate=24000). Excluded for Arabic (no Arabic voice available)
- **Azure TTS removed** from TTS chain (remains STT-only)
- **Dynamic primary selection**: `TTS_PRIMARY` env var (default `cartesia`) chooses runtime primary provider; fallback order: elevenlabs → cartesia → inworld → smallestai
- **Chaos toggles** only break the selected primary (not always elevenlabs)
- **livekit-agents extras**: added `inworld`, `smallestai`; Cartesia model bumped `sonic-2` → `sonic-3`
- **Config**: `language_presets.py` with BCP-47 codes; 8 new TTS settings in `settings.py`
