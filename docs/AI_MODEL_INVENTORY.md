# AI Model Inventory

**Platform:** Telecom AI Voice Agent  
**Date:** 2026-07-04  
**Last updated:** 2026-07-04 — Model reconfiguration: Gemini 2.5 Flash primary LLM; NVIDIA NIM + Groq fallbacks; Gladia STT fallback; Cartesia TTS fallback; language preset KeyError bug fixed.

---

## 1. Speech-to-Text (STT)

### Architecture
```
FallbackAdapter([primary, (gladia), (azure)])
  ├── primary:  deepgram.STT          [DEEPGRAM_API_KEY — live key present]
  ├── fallback: gladia.STT            [GLADIA_API_KEY — optional, skipped if absent]
  └── fallback: azure.STT             [AZURE_SPEECH_KEY — optional, skipped if absent]
```
Providers without a key are silently skipped at build time so the chain degrades gracefully.
Arabic routes to Deepgram `language="ar"` (single-language model) — never `"multi"`.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `nova-3` | `settings.py` — `stt_model: str = Field("nova-3", alias="STT_MODEL")` |
| **Primary provider** | Deepgram (`livekit.plugins.deepgram`) | `providers/stt.py` — `deepgram.STT(model=..., language=...)` |
| **Fallback-1 provider** | Gladia (`livekit.plugins.gladia`) | `providers/stt.py` — `gladia.STT(language=..., api_key=...)` — skipped if `GLADIA_API_KEY` absent |
| **Fallback-2 provider** | Azure Speech (`livekit.plugins.azure`) | `providers/stt.py` — `azure.STT(language=...)` — skipped if `AZURE_SPEECH_KEY` absent |
| **Per-language config** | `config/language_presets.py` — all 4 keys now correct | Fixed — see §9 |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `providers/_resilience.py` |
| **API key env var** | `DEEPGRAM_API_KEY` | Live key present in `.env` |
| **Gladia API key** | `GLADIA_API_KEY` | Empty — add to activate |
| **Azure API keys** | `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | Empty — add to activate |

---

## 2. Text-to-Speech (TTS)

### Architecture
```
FallbackAdapter([primary, (cartesia), (azure)])
  ├── primary:  elevenlabs.TTS        [ELEVEN_API_KEY — required]
  ├── fallback: cartesia.TTS          [CARTESIA_API_KEY — optional, skipped if absent]
  └── fallback: azure.TTS             [AZURE_SPEECH_KEY — optional, skipped if absent]
```

### NOTE on Deepgram TTS
The installed LiveKit plugin bundle (`livekit-agents[deepgram,...]==1.6.3`) exposes only
`deepgram.STT` — there is no `deepgram.TTS` in this version of the plugin.
Deepgram's Aura TTS REST product exists but is not surfaced as a `tts.TTS`-compatible object.
Therefore:
- **Deepgram is used as STT primary only.**
- **ElevenLabs remains TTS primary** (uses `ELEVEN_API_KEY`).
- **Cartesia is wired as TTS fallback-1** (uses `CARTESIA_API_KEY`). Active: key present in `.env`.
- **Azure is TTS final fallback** (uses `AZURE_SPEECH_KEY`). Inactive — no key.

When a future `livekit-plugins-deepgram` release adds `deepgram.TTS`, promote it to primary and demote ElevenLabs to fallback in `providers/tts.py`.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `eleven_flash_v2_5` | `settings.py` — `tts_model` |
| **Primary voice ID** | `EXAVITQu4vr4xnSDxMaL` | `settings.py` — `eleven_voice_id` |
| **Primary provider** | ElevenLabs (`livekit.plugins.elevenlabs`) | `providers/tts.py` — `elevenlabs.TTS(model=..., voice_id=..., language=...)` |
| **Fallback-1 provider** | Cartesia (`livekit.plugins.cartesia`) | `providers/tts.py` — `cartesia.TTS(model=..., voice=...)` — skipped if `CARTESIA_API_KEY` absent |
| **Fallback-2 provider** | Azure Neural TTS (`livekit.plugins.azure`) | `providers/tts.py` — `azure.TTS(voice=...)` — skipped if `AZURE_SPEECH_KEY` absent |
| **Deepgram TTS fields** | `DEEPGRAM_TTS_MODEL=aura-asteria-en` | Documented in settings for future use when plugin supports it |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `providers/_resilience.py` |
| **Cartesia API key** | `CARTESIA_API_KEY` | Present in `.env` — activate by adding key |
| **Cartesia model** | `sonic-2` | `settings.py` — `cartesia_tts_model` |
| **Cartesia voice IDs** | Per-language UUIDs in `language_presets.py` | `preset["cartesia_voice_id"]` |

---

## 3. Large Language Model (LLM)

### Architecture
```
FallbackAdapter([primary, (nvidia), (openai), (groq)])
  ├── primary:  google.LLM            [GOOGLE_API_KEY — live key present]
  ├── fallback: NvidiaLLM             [NVIDIA_API_KEY — optional, skipped if absent]
  ├── fallback: openai.LLM            [OPENAI_API_KEY — optional, skipped if absent]
  └── fallback: GroqLLM               [GROQ_API_KEY   — optional, skipped if absent]
```
Providers without a key are silently skipped — the chain is built dynamically in `build_llm()`.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Primary model ID** | `gemini-2.5-flash-latest` | `settings.py` — `llm_primary_model` / `LLM_PRIMARY_MODEL` |
| **Primary provider** | Google Gemini (`livekit.plugins.google`) | `providers/llm.py` — `google.LLM(model=...)` |
| **Fallback-1 provider** | NVIDIA NIM (`providers/nvidia_adapter.NvidiaLLM`) | Skipped if `NVIDIA_API_KEY` absent |
| **Fallback-1 model ID** | `meta/llama-3.1-8b-instruct` | `NVIDIA_MODEL` env var |
| **Fallback-2 provider** | OpenAI GPT (`livekit.plugins.openai`) | Skipped if `OPENAI_API_KEY` absent |
| **Fallback-2 model ID** | `gpt-4o-mini` | `settings.py` — `llm_fallback_model` / `LLM_FALLBACK_MODEL` |
| **Fallback-3 provider** | Groq (`providers/groq_adapter.GroqLLM`) | Skipped if `GROQ_API_KEY` absent |
| **Fallback-3 model ID** | `llama3-8b-8192` | `GROQ_MODEL` env var |
| **Chaos model (test)** | `chaos-invalid-model-does-not-exist` | `providers/_resilience.py` |
| **Primary API key** | `GOOGLE_API_KEY` | Live key present |
| **NVIDIA API key** | `NVIDIA_API_KEY` | Empty — add to activate |
| **OpenAI API key** | `OPENAI_API_KEY` | Empty — add to activate |
| **Groq API key** | `GROQ_API_KEY` | Empty — add to activate |

### NVIDIA NIM Adapter Design
- **File**: `apps/agent-worker/src/providers/nvidia_adapter.py`
- **Implementation**: Subclasses `livekit.plugins.openai.LLM` with `base_url="https://integrate.api.nvidia.com/v1"`.
- **Rationale**: NIM is OpenAI-compatible, so reusing the LiveKit OpenAI plugin gives full FallbackAdapter + streaming compatibility with zero additional code.
- **Constraints**: One key (`NVIDIA_API_KEY`), one model (`NVIDIA_MODEL`), no pool.

### Groq Adapter Design
- **File**: `apps/agent-worker/src/providers/groq_adapter.py`
- **Implementation**: Subclasses `livekit.plugins.openai.LLM` with `base_url="https://api.groq.com/openai/v1"`.
- **Rationale**: Groq is OpenAI-compatible — same pattern as NVIDIA adapter.
- **Constraints**: One key (`GROQ_API_KEY`), one model (`GROQ_MODEL`), no pool.

---

## 4. Voice Activity Detection (VAD)

### Architecture
Silero VAD (local, CPU-only, no API key needed).

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | Silero VAD (`livekit.plugins.silero`) | `providers/vad.py` — `silero.VAD.load(min_silence_duration=...)` |
| **Model** | Built-in Silero model | Loaded automatically |
| **Min silence threshold** | `0.25` seconds | `settings.py` — `vad_min_silence` / `VAD_MIN_SILENCE` |

---

## 5. Turn Detection

### Architecture
Audio-native End-of-Utterance (EOU) detection via LiveKit's MultilingualModel. Runs locally, no API key.

### Models & Configuration

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | `livekit.plugins.turn_detector.multilingual` | `providers/turn_detection.py` |
| **Model** | `MultilingualModel()` | Supports fr/ar/en natively |
| **Configuration** | None (no parameters) | Local CPU |

---

## 6. Noise Cancellation (Optional — disabled by default)

| Item | Value | Where Defined |
|---|---|---|
| **Provider** | `livekit.plugins.noise_cancellation` | `providers/noise_cancellation.py` |
| **Enabled** | `False` by default | `settings.py` — `noise_cancellation` / `NOISE_CANCELLATION` |
| **Requirements** | May require LiveKit Cloud | Comment in `noise_cancellation.py` |
| **Graceful degradation** | Returns `None` if unavailable | `noise_cancellation.py` |

---

## 7. Embeddings (RAG / Knowledge Search)

| Item | Value | Where Defined |
|---|---|---|
| **Embedding model ID** | `text-embedding-3-small` | `services/knowledge-service/src/knowledge_service/retriever.py` |
| **API endpoint** | `https://api.openai.com/v1/embeddings` | `retriever.py` |
| **Vector dimensions** | 1536 | Depends on model |
| **API key env var** | `OPENAI_API_KEY` | `retriever.py` |
| **Vector store** | Qdrant | `retriever.py` |
| **Collection name** | `telecom_knowledge` | `QDRANT_COLLECTION` |

---

## 8. Session Pipeline Assembly

All models are composed into a session in one place:

| File | Line | What it does |
|---|---|---|
| `providers/session_factory.py` | 29–36 | `AgentSession(vad=..., turn_detection=..., stt=..., llm=..., tts=...)` |
| `providers/session_factory.py` | 22 | Accepts `Settings` + language code (`fr`/`ar`/`en`) |
| `providers/session_factory.py` | 28 | Resolves language preset from `LANGUAGE_PRESETS` |

---

## 9. Language Presets — FIXED ✅

**File:** `apps/agent-worker/src/config/language_presets.py`

The preset dictionary previously contained incorrect key names causing `KeyError` at runtime in both the STT and TTS builders. This has been fixed.

### Current (correct) preset keys:
```python
LANGUAGE_PRESETS = {
    "fr": {
        "deepgram_language": "fr",           # deepgram.STT(language=...)
        "azure_stt_locale":  "fr-FR",        # azure.STT(language=...)
        "gladia_language":   "fr",           # gladia.STT(language=...)
        "tts_iso":           "fr",           # elevenlabs.TTS(language=...)
        "azure_tts_voice":   "fr-FR-DeniseNeural",  # azure.TTS(voice=...)
        "cartesia_voice_id": "a249eaff-...", # cartesia.TTS(voice=...)
    },
    # ... ar, en same shape
}
```
Arabic uses `"deepgram_language": "ar"` (single-language model, never `"multi"`).

---

## 10. Model Configuration Chain Summary

```
.env                 →  LLM_PRIMARY_MODEL=gemini-2.5-flash-latest
                          LLM_FALLBACK_MODEL=gpt-4o-mini
                          STT_MODEL=nova-3
                          TTS_MODEL=eleven_flash_v2_5
                          ELEVEN_VOICE_ID=EXAVITQu4vr4xnSDxMaL
                          NVIDIA_MODEL=meta/llama-3.1-8b-instruct
                          GROQ_MODEL=llama3-8b-8192
                          CARTESIA_TTS_MODEL=sonic-2
                          NOISE_CANCELLATION=False / VAD_MIN_SILENCE=0.25
                            │
                            ▼
settings.py          →  Settings class (pydantic) parses env vars
                            │
                            ▼
session_factory.py   →  build_agent_session(Settings, language)
                          calls build_stt / build_llm / build_tts / build_vad
                            │
                            ▼ (per builder)
stt.py               →  deepgram.STT(model=..., language=preset["deepgram_language"])
                          └─ fallback: gladia.STT(language=preset["gladia_language"])      [if key]
                          └─ fallback: azure.STT(language=preset["azure_stt_locale"])     [if key]
tts.py               →  elevenlabs.TTS(model=..., voice_id=..., language=preset["tts_iso"])
                          └─ fallback: cartesia.TTS(model=..., voice=preset["cartesia_voice_id"]) [if key]
                          └─ fallback: azure.TTS(voice=preset["azure_tts_voice"])         [if key]
llm.py               →  google.LLM(model=LLM_PRIMARY_MODEL)
                          └─ fallback: NvidiaLLM(model=NVIDIA_MODEL)                       [if key]
                          └─ fallback: openai.LLM(model=LLM_FALLBACK_MODEL)               [if key]
                          └─ fallback: GroqLLM(model=GROQ_MODEL)                          [if key]
vad.py               →  silero.VAD.load(min_silence_duration=VAD_MIN_SILENCE)
turn_detection.py    →  MultilingualModel()
noise_cancellation.py → BVC()  (only if NOISE_CANCELLATION=True)
```

---

## 11. Provider API Key Map

| Provider | Role | API Key env var | Status |
|---|---|---|---|
| Deepgram | STT primary | `DEEPGRAM_API_KEY` | **Live key present** |
| Gladia | STT fallback-1 | `GLADIA_API_KEY` | Empty — add to activate |
| Azure | STT fallback-2 / TTS fallback-2 | `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` | Empty — add to activate |
| Google Gemini | LLM primary | `GOOGLE_API_KEY` | **Live key present** |
| NVIDIA NIM | LLM fallback-1 | `NVIDIA_API_KEY` | Empty — add to activate |
| OpenAI GPT | LLM fallback-2 | `OPENAI_API_KEY` | Empty — add to activate |
| Groq | LLM fallback-3 | `GROQ_API_KEY` | Empty — add to activate |
| ElevenLabs | TTS primary | `ELEVEN_API_KEY` | Empty — add to activate |
| Cartesia | TTS fallback-1 | `CARTESIA_API_KEY` | Key present in `.env` — add to activate |
| Silero | VAD | None (local) | Active |
| Turn Detector | EOU | None (local) | Active |
| BVC | Noise cancellation | None (local, may need LiveKit Cloud) | Disabled |

---

## 12. New Files Added

| File | Purpose |
|---|---|
| `apps/agent-worker/src/providers/nvidia_adapter.py` | NVIDIA NIM LLM adapter (subclasses `openai.LLM` with NIM base URL) |
| `apps/agent-worker/src/providers/groq_adapter.py` | Groq LLM adapter (subclasses `openai.LLM` with Groq base URL) |

## 13. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| `livekit-plugins-deepgram==1.6.3` exposes only `deepgram.STT` — no `deepgram.TTS` | Deepgram cannot be used as TTS primary | ElevenLabs is TTS primary; Deepgram TTS fields documented for future use |
| `ELEVEN_API_KEY` currently empty | TTS primary will fail at runtime until key is added | Add ElevenLabs key or Cartesia key (`CARTESIA_API_KEY` is present) |
| Cartesia voice IDs in presets are placeholder UUIDs | May need to be replaced with real Cartesia voice IDs for your account | Update `language_presets.py` with actual IDs from Cartesia dashboard |