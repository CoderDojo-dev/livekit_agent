# version_49 — Multi-TTS Provider Expansion (Inworld + Smallest.ai) + Dynamic Primary Selection

## Summary
This version rewrites the TTS subsystem to support **4 concurrent TTS providers** with **dynamic runtime primary selection** through a `FallbackAdapter`. Previously the chain was fixed: ElevenLabs primary → Cartesia → Azure. Now the agent auto-selects a primary (configurable via `TTS_PRIMARY`), with the other providers as ordered fallbacks. Azure TTS is removed (no credits); it remains STT-only.

## New TTS Providers Added

### Inworld (`inworld.TTS`)
- **Env var**: `INWORLD_API_KEY` (Base64-encoded key from platform.inworld.ai)
- **Model**: `inworld-tts-2` (configurable via `INWORLD_TTS_MODEL`)
- **Voice**: `alain` (configurable via `INWORLD_VOICE_ID`)
- **Language**: BCP-47 (fr-FR, en-US, ar) via new `inworld_language` field in `LANGUAGE_PRESETS`
- **French quality**: GA (production-ready), expressive

### Smallest.ai (`smallestai.TTS`)
- **Env var**: `SMALLEST_API_KEY`
- **Model**: `lightning_v3.1` (configurable via `SMALLEST_TTS_MODEL` — standard, not `_pro`)
- **Voice**: `juliette` (configurable via `SMALLEST_VOICE_ID`)
- **Sample rate**: 24000 Hz
- **Arabic excluded**: Smallest.ai has no Arabic voice — the factory returns `None` for `tts_iso="ar"`, so Arabic callers never exercise this provider
- **French quality**: Beta (fastest provider)

### Azure TTS Removed
- `azure.TTS` removed from the TTS chain — no account/crédits available
- `AZURE_SPEECH_KEY` remains for **STT only** (see `stt.py`)

## Dynamic Primary Selection

**`TTS_PRIMARY`** env var (default: `cartesia`) controls which provider runs first in the `FallbackAdapter`:
- At runtime, `TTS_PRIMARY` is read from the environment
- The selected primary is placed at index 0; remaining providers follow the quality order: `elevenlabs → cartesia → inworld → smallestai`
- **Chaos (`CHAOS_BREAK_TTS`) now targets only the selected primary**, not hard-coded ElevenLabs — so resilience tests exercise the real fallback path regardless of which provider is primary
- If `TTS_PRIMARY` is set to an unrecognized value, a warning is logged and `cartesia` is used as fallback

Provider inclusion is **key-gated**: each provider is built only if its API key env var is present. Providers without keys are silently skipped.

## SDK / Library Version Changes

### `livekit-agents` extras expanded
- **Before**: `livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia]==1.6.5`
- **After**: `...cartesia,inworld,smallestai]==1.6.5`
- No version bump (still 1.6.5), but `inworld` and `smallestai` extras now included

### Cartesia Model Bumped
- `CARTESIA_TTS_MODEL` default changed from `sonic-2` to **`sonic-3`**

## No Container Changes
No Dockerfile, docker-compose, or new services in this version — purely agent-worker configuration and TTS logic.

## Config Changes

### `.env.example`
New TTS section with:
- `TTS_PRIMARY=cartesia` — dynamic primary selection
- `INWORLD_API_KEY`, `INWORLD_TTS_MODEL`, `INWORLD_VOICE_ID` — Inworld configuration
- `SMALLEST_API_KEY`, `SMALLEST_TTS_MODEL`, `SMALLEST_VOICE_ID` — Smallest.ai configuration
- `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE` — **placeholders only** (Gemini TTS not wired: plugin is beta with `streaming=False`, unsuitable for real-time)
- `AZURE_SPEECH_KEY` comment updated: now STT-only

### `settings.py`
8 new fields: `tts_primary`, `inworld_api_key`, `inworld_tts_model`, `inworld_voice_id`, `smallest_api_key`, `smallest_tts_model`, `smallest_voice_id`, `gemini_tts_model`, `gemini_tts_voice`

### `language_presets.py`
New `inworld_language` key per language (BCP-47: `fr-FR`, `ar`, `en-US`)

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `apps/agent-worker/src/providers/tts.py` | MODIFIED | 4-provider FallbackAdapter; dynamic primary; Inworld + Smallest.ai; Azure removed |
| `apps/agent-worker/pyproject.toml` | MODIFIED | Added inworld, smallestai extras to livekit-agents |
| `apps/agent-worker/src/config/settings.py` | MODIFIED | 9 new TTS settings fields |
| `apps/agent-worker/src/config/language_presets.py` | MODIFIED | Added inworld_language (BCP-47) per locale |
| `.env.example` | MODIFIED | Full TTS provider config section; Cartesia model sonic-3 |
| `apps/agent-worker/src/clients/nms_client.py` | MODIFIED | Import ordering (ruff fix) |
