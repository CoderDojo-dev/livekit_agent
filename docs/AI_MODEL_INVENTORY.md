# AI Model Inventory

**Platform:** Telecom AI Voice Agent  
**Date:** 2026-07-04

---

## 1. Speech-to-Text (STT)

### Architecture
```
FallbackAdapter([primary, fallback])
  ├── primary: deepgram.STT
  └── fallback: azure.STT
```
If Deepgram fails, Azure takes over transparently via LiveKit's `stt.FallbackAdapter`.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `nova-3` | `apps/agent-worker/src/config/settings.py:32` — `stt_model: str = Field("nova-3", alias="STT_MODEL")` |
| **Provider** | Deepgram (livekit.plugins.deepgram) | `apps/agent-worker/src/providers/stt.py:16` — `deepgram.STT(model=..., language=...)` |
| **Fallback provider** | Azure Speech-to-Text (livekit.plugins.azure) | `apps/agent-worker/src/providers/stt.py:20` — `azure.STT(language=...)` |
| **Per-language config** | `language_presets.py:5-9` → **BUG: wrong key names** (see §7 below) | `apps/agent-worker/src/config/language_presets.py` |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `apps/agent-worker/src/providers/_resilience.py:9` |
| **API key env var** | `DEEPGRAM_API_KEY` | Read by `deepgram.STT` from environment |

### Deepgram models referenced in code
The ONLY Deepgram model ID hardcoded or configured is `nova-3` (the default in settings.py). It can be overridden via `STT_MODEL` in `.env`.

---

## 2. Text-to-Speech (TTS)

### Architecture
```
FallbackAdapter([primary, fallback])
  ├── primary: elevenlabs.TTS
  └── fallback: azure.TTS (Neural)
```
If ElevenLabs fails, Azure Neural TTS takes over.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `eleven_flash_v2_5` | `apps/agent-worker/src/config/settings.py:34` — `tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")` |
| **Primary voice ID** | `EXAVITQu4vr4xnSDxMaL` | `apps/agent-worker/src/config/settings.py:35` — `eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")` |
| **Primary provider** | ElevenLabs (livekit.plugins.elevenlabs) | `apps/agent-worker/src/providers/tts.py:15` — `elevenlabs.TTS(model=..., voice_id=..., language=...)` |
| **Fallback provider** | Azure Neural TTS (livekit.plugins.azure) | `apps/agent-worker/src/providers/tts.py:20` — `azure.TTS(voice=...)` |
| **Per-language Azure voice** | `language_presets.py:5-9` → **BUG: wrong key names** (see §7) | `apps/agent-worker/src/config/language_presets.py` |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `apps/agent-worker/src/providers/_resilience.py:9` |
| **API key env var** | `ELEVEN_API_KEY` | Read by `elevenlabs.TTS` from environment |
| **Fallback API key env var** | `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | Read by `azure.TTS` from environment |

---

## 3. Large Language Model (LLM)

### Architecture
```
FallbackAdapter([primary, fallback])
  ├── primary: openai.LLM
  └── fallback: google.LLM (Gemini)
```
If OpenAI fails, Gemini takes over.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `gpt-4.1-mini` | `apps/agent-worker/src/config/settings.py:37` — `llm_primary_model: str = Field("gpt-4.1-mini", alias="LLM_PRIMARY_MODEL")` |
| **Fallback model ID** | `gemini-2.0-flash` | `apps/agent-worker/src/config/settings.py:38` — `llm_fallback_model: str = Field("gemini-2.0-flash", alias="LLM_FALLBACK_MODEL")` |
| **Primary provider** | OpenAI (livekit.plugins.openai) | `apps/agent-worker/src/providers/llm.py:16` — `openai.LLM(model=...)` |
| **Fallback provider** | Google Gemini (livekit.plugins.google) | `apps/agent-worker/src/providers/llm.py:17` — `google.LLM(model=...)` |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `apps/agent-worker/src/providers/_resilience.py:9` |
| **API key env var** | `OPENAI_API_KEY` | Read by `openai.LLM` from environment |
| **Fallback API key env var** | `GOOGLE_API_KEY` | Read by `google.LLM` from environment |

---

## 4. Voice Activity Detection (VAD)

### Architecture
Silero VAD (local, CPU-only, no API key needed).

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | Silero VAD (livekit.plugins.silero) | `apps/agent-worker/src/providers/vad.py:12` — `silero.VAD.load(min_silence_duration=...)` |
| **Model** | Built-in Silero model (bundled in livekit-plugins-silero package) | Not configurable — loaded automatically by `silero.VAD.load()` |
| **Min silence threshold** | `0.25` seconds | `apps/agent-worker/src/config/settings.py:41` — `vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")` |

---

## 5. Turn Detection

### Architecture
Audio-native End-of-Utterance (EOU) detection via LiveKit's MultilingualModel. Runs locally, no API key.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | livekit.plugins.turn_detector.multilingual | `apps/agent-worker/src/providers/turn_detection.py:13-14` — `from livekit.plugins.turn_detector.multilingual import MultilingualModel` |
| **Model** | `MultilingualModel()` | Supports fr/ar/en natively, runs on local CPU |
| **Configuration** | None (no parameters) | `apps/agent-worker/src/providers/turn_detection.py:14` |

---

## 6. Noise Cancellation (Optional — disabled by default)

### Architecture
BVC (Background Voice Cancellation). Only activates when `NOISE_CANCELLATION=True` in `.env`.

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | livekit.plugins.noise_cancellation | `apps/agent-worker/src/providers/noise_cancellation.py:19-21` — `noise_cancellation.BVC()` |
| **Enabled** | `False` by default | `apps/agent-worker/src/config/settings.py:43` — `noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")` |
| **Requirements** | May require LiveKit Cloud | Comment in `noise_cancellation.py:3` — "[VERIFY] BVC may require livekit-plugins-noise-cancellation and LiveKit Cloud" |
| **Graceful degradation** | Returns `None` if unavailable | `noise_cancellation.py:23` — returns None with warning |

---

## 7. Embeddings (RAG / Knowledge Search)

### Architecture
OpenAI embeddings API → Qdrant vector store. Falls back to lexical (keyword) search if Qdrant is unavailable.

| Item | Value | Where Defined |
|---|---|---|
| **Embedding model ID** | `text-embedding-3-small` | `services/knowledge-service/src/knowledge_service/retriever.py:79` — `model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")` |
| **API endpoint** | `https://api.openai.com/v1/embeddings` | `services/knowledge-service/src/knowledge_service/retriever.py:83-85` |
| **Vector dimensions** | 1536 (determined by OpenAI model) | Implicit — depends on model |
| **API key env var** | `OPENAI_API_KEY` | `services/knowledge-service/src/knowledge_service/retriever.py:78` — `api_key = os.environ["OPENAI_API_KEY"]` |
| **Vector store** | Qdrant (`qdrant-client>=1.12`) | `services/knowledge-service/src/knowledge_service/retriever.py:100` |
| **Collection name** | `telecom_knowledge` (env: `QDRANT_COLLECTION`) | `services/knowledge-service/src/knowledge_service/retriever.py:101` |

---

## 8. Session Pipeline Assembly

All models are composed into a session in one place:

| File | Line | What it does |
|---|---|---|
| `apps/agent-worker/src/providers/session_factory.py` | 29-36 | `AgentSession(vad=..., turn_detection=..., stt=..., llm=..., tts=...)` |
| `apps/agent-worker/src/providers/session_factory.py` | 22 | Accepts `Settings` + language code (`fr`/`ar`/`en`) |
| `apps/agent-worker/src/providers/session_factory.py` | 28 | Resolves language preset from `LANGUAGE_PRESETS` |

---

## 9. Language Presets — CRITICAL BUG

**File:** `apps/agent-worker/src/config/language_presets.py:5-9`

### Current (broken) preset keys:
```python
LANGUAGE_PRESETS = {
    "fr": {"stt_language": "fr",   "tts_voice": "fr"},
    "ar": {"stt_language": "ar",   "tts_voice": "ar"},
    "en": {"stt_language": "en",   "tts_voice": "en"},
}
```

### What the STT builder reads:
```python
# stt.py:18
primary = deepgram.STT(language=preset["deepgram_language"])   # ❌ KeyError — key doesn't exist
# stt.py:20
fallback = azure.STT(language=preset["azure_stt_locale"])       # ❌ KeyError — key doesn't exist
```

### What the TTS builder reads:
```python
# tts.py:18
primary = elevenlabs.TTS(language=preset["tts_iso"])            # ❌ KeyError — key doesn't exist
# tts.py:20
fallback = azure.TTS(voice=preset["azure_tts_voice"])           # ❌ KeyError — key doesn't exist
```

### Summary: 4 missing keys
| Preset has | Builder reads | Used by |
|---|---|---|
| `stt_language` | `deepgram_language` | Deepgram STT language parameter |
| *(missing)* | `azure_stt_locale` | Azure STT locale |
| `tts_voice` | `azure_tts_voice` | Azure Neural TTS voice name |
| *(missing)* | `tts_iso` | ElevenLabs TTS ISO language code |

**The preset needs to provide all 4 keys:**
```python
LANGUAGE_PRESETS = {
    "fr": {
        "deepgram_language": "fr",
        "azure_stt_locale": "fr-FR",
        "tts_iso": "fr",
        "azure_tts_voice": "fr-FR-DeniseNeural",    # or similar Azure voice
    },
    "ar": {
        "deepgram_language": "ar",
        "azure_stt_locale": "ar-EG",
        "tts_iso": "ar",
        "azure_tts_voice": "ar-EG-SalmaNeural",      # or similar
    },
    "en": {
        "deepgram_language": "en",
        "azure_stt_locale": "en-US",
        "tts_iso": "en",
        "azure_tts_voice": "en-US-JennyNeural",       # or similar
    },
}
```

---

## 10. Model Configuration Chain Summary

```
.env                  →  STT_MODEL=nova-3
                          TTS_MODEL=eleven_flash_v2_5
                          ELEVEN_VOICE_ID=EXAVITQu4vr4xnSDxMaL
                          LLM_PRIMARY_MODEL=gpt-4.1-mini
                          LLM_FALLBACK_MODEL=gemini-2.0-flash
                          EMBEDDING_MODEL=text-embedding-3-small
                          NOISE_CANCELLATION=False
                          VAD_MIN_SILENCE=0.25
                          CHAOS_BREAK_STT/LLM/TTS=False
                            │
                            ▼
settings.py           →  Settings class (pydantic) parses env vars
                            │
                            ▼
session_factory.py    →  build_agent_session(Settings, language)
                          calls build_stt / build_llm / build_tts / build_vad
                            │
                            ▼ (per builder)
stt.py                →  deepgram.STT(model=..., language=preset["deepgram_language"])
                          └─ fallback: azure.STT(language=preset["azure_stt_locale"])
tts.py                →  elevenlabs.TTS(model=..., voice_id=..., language=preset["tts_iso"])
                          └─ fallback: azure.TTS(voice=preset["azure_tts_voice"])
llm.py                →  openai.LLM(model=LLM_PRIMARY_MODEL)
                          └─ fallback: google.LLM(model=LLM_FALLBACK_MODEL)
vad.py                →  silero.VAD.load(min_silence_duration=VAD_MIN_SILENCE)
turn_detection.py     →  MultilingualModel()
noise_cancellation.py →  BVC()  (only if NOISE_CANCELLATION=True)
                            │
                            ▼
language_presets.py ← **BUG: keys don't match** → STT/TTS builders get KeyError at runtime
```

---

## 11. Provider API Key Map

| Provider | Model chain | API Key env var |
|---|---|---|
| Deepgram | STT primary | `DEEPGRAM_API_KEY` |
| ElevenLabs | TTS primary | `ELEVEN_API_KEY` |
| Azure | STT fallback + TTS fallback | `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` |
| OpenAI | LLM primary + Embeddings (RAG) | `OPENAI_API_KEY` |
| Google | LLM fallback (Gemini) | `GOOGLE_API_KEY` |
| Silero | VAD | None (local) |
| Turn Detector | EOU | None (local) |
| BVC | Noise cancellation | None (local, but may require LiveKit Cloud) |