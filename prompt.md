# Backend Engineering Prompt — Telecom AI Agent Platform

> **Objective**: Apply all backend configuration improvements and model provider changes described below. Do NOT change existing business logic or agent behavior — changes are localized to configuration, provider adapters, and language preset key names.

---


# Backend Engineering Task: Voice AI Model Reconfiguration & Adapter Integration

## Role / Persona
You are an expert backend engineer specialized in Python AI agent systems, FastAPI monorepos, and multi-provider LLM/STT/TTS integrations. Work in the repository **without breaking existing behavior**; prefer small, additive changes and clear separation of concerns.

## Repository Context
Project: `telecom-ai-agent-platform` (LiveKit Agents-based voice AI platform for telecom support).
Voice/runtime entry point: `apps/agent-worker/src/`. Shared packages: `packages/`.
Infrastructure: local Docker Compose with PostgreSQL, Redis, Qdrant, MinIO, optional LiveKit.

## High-Level Goal
Reconfigure the voice agent's model hierarchy so that it uses the credentials the project owner actually has today (Deepgram for audio, Google Gemini 2.5 Flash for text), and add optional NVIDIA NIM + Groq adapters that can later be enabled by switching `.env` variables.

---

## 1. LLM Model Switch

### Current State
- **Primary LLM**: OpenAI `gpt-4o-mini` configured in `apps/agent-worker/src/config/settings.py:37`, used via `apps/agent-worker/src/providers/llm.py:16` (`openai.LLM`).
- **Fallback LLM**: Google Gemini `gemini-2.0-flash` configured in `apps/agent-worker/src/config/settings.py:38`, used via `apps/agent-worker/src/providers/llm.py:17` (`google.LLM`).
- Env vars: `OPENAI_API_KEY` and `GOOGLE_API_KEY`.

### Required Change
Make **Google Gemini 2.5 Flash** the **primary** LLM and **OpenAI GPT** the **fallback**.

### Details
1. Update `apps/agent-worker/src/config/settings.py`:
   - Change `llm_primary_model` default from `gpt-4o-mini` to `gemini-2.5-flash-latest` (or the exact stable model ID you determine for Gemini 2.5 Flash).
   - Change `llm_fallback_model` default from `gemini-2.0-flash` to `gpt-4o-mini`.
   - Keep env aliases `LLM_PRIMARY_MODEL` and `LLM_FALLBACK_MODEL`.
2. Update `apps/agent-worker/src/providers/llm.py`:
   - Swap the builder order so Gemini is primary and OpenAI is fallback inside `llm_module.FallbackAdapter([primary, fallback])`.
   - Keep `chaos_model(...)` logic intact.
   - Do **not** change the function signature of `build_llm()`.
3. Update root `.env.example` and current `.env` so that:
   - `LLM_PRIMARY_MODEL=gemini-2.5-flash-latest`
   - `LLM_FALLBACK_MODEL=gpt-4o-mini`
   - `GOOGLE_API_KEY` is documented as the active primary key.
   - `OPENAI_API_KEY` remains documented as fallback.
4. Validate: `python -c "from providers.llm import build_llm; from config.settings import get_settings; build_llm(get_settings().llm_primary_model, get_settings().llm_fallback_model)"` should produce an `llm_module.FallbackAdapter` with Gemini primary.

### Constraints
- Do **not** introduce a separate LLM microservice.
- Do **not** break the fallback pattern.
- Keep the same import paths and module locations.

---

## 2. STT / TTS Model Switch — Deepgram as Primary

### Current State
- STT: `apps/agent-worker/src/providers/stt.py`
  - Primary: `deepgram.STT(model=settings.stt_model)`
  - Fallback: `azure.STT(...)`
  - Reads preset keys `deepgram_language` and `azure_stt_locale` from `LANGUAGE_PRESETS`.
- TTS: `apps/agent-worker/src/providers/tts.py`
  - Primary: `elevenlabs.TTS(model=settings.tts_model, voice_id=...)`
  - Fallback: `azure.TTS(voice=...)`
  - Reads preset keys `tts_iso` and `azure_tts_voice`.
- Config defaults in `apps/agent-worker/src/config/settings.py`: `stt_model="nova-3"`, `tts_model="eleven_flash_v2_5"`, `eleven_voice_id="EXAVITQu4vr4xnSDxMaL"`.
- `LANGUAGE_PRESETS` in `apps/agent-worker/src/config/language_presets.py` currently uses wrong keys:
  ```python
  LANGUAGE_PRESETS = {
      "fr": {"stt_language": "fr",   "tts_voice": "fr"},
      "ar": {"stt_language": "ar",   "tts_voice": "ar"},
      "en": {"stt_language": "en",   "tts_voice": "en"},
  }
  ```
- The builders expect:
  - STT: `preset["deepgram_language"]`, `preset["azure_stt_locale"]`
  - TTS: `preset["tts_iso"]`, `preset["azure_tts_voice"]`
- This mismatch causes a `KeyError` at runtime.

### Required Changes
1. Fix `apps/agent-worker/src/config/language_presets.py`:
   - Replace the preset dictionary with all four keys that the builders read.
   - Provide sensible values for the three supported languages (`fr`, `ar`, `en`).
   - Keep Arabic using a single-language Deepgram model (`language="ar"`, never `"multi"`) as documented in `stt.py`.
   Example shape:
   ```python
   LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
       "fr": {
           "deepgram_language": "fr",
           "azure_stt_locale": "fr-FR",
           "tts_iso": "fr",
           "azure_tts_voice": "fr-FR-DeniseNeural",
       },
       "ar": {
           "deepgram_language": "ar",
           "azure_stt_locale": "ar-EG",
           "tts_iso": "ar",
           "azure_tts_voice": "ar-EG-SalmaNeural",
       },
       "en": {
           "deepgram_language": "en",
           "azure_stt_locale": "en-US",
           "tts_iso": "en",
           "azure_tts_voice": "en-US-JennyNeural",
       },
   }
   ```
2. In `apps/agent-worker/src/providers/stt.py`:
   - Keep Deepgram as primary STT.
   - Keep Azure as fallback.
   - After the preset fix, no code change is strictly necessary, but verify the file still works with the new keys.
3. In `apps/agent-worker/src/providers/tts.py`:
   - Reorder providers so **Deepgram is primary TTS**, and ElevenLabs + Azure become fallbacks behind a `FallbackAdapter([primary_deepgram, fallback_elevenlabs_or_azure])`.
   - The user has a Deepgram API key with credits and wants fallback options only after Deepgram.
   - If Deepgram does **not** support TTS with the same API key/model configured, decide one of the following and document it clearly:
     a) Use Deepgram TTS if the installed LiveKit plugin supports it (`livekit.plugins.deepgram.tts` or similar); or
     b) If Deepgram cannot act as TTS provider with the current SDK, keep **ElevenLabs as the displayed primary in practice** but configure it to use the Deepgram STT key, and add Azure as fallback — but **report this explicitly to the user**.
   - In either case, the `.env` must contain `DEEPGRAM_API_KEY`, and the system must read it.
4. In `apps/agent-worker/src/config/settings.py`:
   - Add env-driven defaults needed for Deepgram TTS if any (e.g., `DEEPGRAM_TTS_MODEL`, `DEEPGRAM_TTS_VOICE`), keeping sensible defaults.
   - Keep `ELEVEN_API_KEY` and `AZURE_SPEECH_KEY` as documented fallbacks.
5. Update root `.env.example`:
   - `DEEPGRAM_API_KEY=...` (existing)
   - `ELEVEN_API_KEY=` (fallback, empty)
   - `AZURE_SPEECH_KEY=` / `AZURE_SPEECH_REGION=` (fallback, empty)
   - Add `DEEPGRAM_TTS_MODEL=` if needed.
6. Verify credentials are read correctly:
   - Confirm `load_dotenv()` is called at agent startup.
   - Confirm `DEEPGRAM_API_KEY` is visible to `livekit.plugins.deepgram`.

### Constraints
- Do **not** remove ElevenLabs or Azure code — keep them as fallbacks.
- The three supported languages (`fr`, `ar`, `en`) must continue to work.
- If Deepgram TTS is unavailable via LiveKit plugins, explain the limitation and implement the closest possible fallback ordering.

---

## 3. Add NVIDIA NIM LLM Adapter

### Context
The user provided reference code from a previous LLM gateway. Use it **only as documentation of the desired behavior**. Constraints:
- **No key pool** — use only one API key read from `.env` (`NVIDIA_API_KEY` or `NVAPI_KEY`).
- **No separate microservice** — the adapter must fit inside `apps/agent-worker/src/providers/llm.py` or an adjacent file.
- **Minimal intrusion** — do not duplicate LiveKit provider logic or change the existing `build_llm()` contract.

### Required Changes
1. Create a new module `apps/agent-worker/src/providers/nvidia_adapter.py`:
   - Implement a thin wrapper compatible with the LiveKit `LLM` interface.
   - Use `httpx.AsyncClient` to call NVIDIA NIM OpenAI-compatible chat completions endpoint:
     - Base URL: `https://integrate.api.nvidia.com/v1`
     - Endpoint: `/chat/completions`
     - Auth: `Authorization: Bearer {NVIDIA_API_KEY}`
   - Support both streaming and non-streaming.
   - Support env-configurable model ID (`NVIDIA_MODEL`, default: `meta/llama-3.1-8b-instruct`).
   - Read timeout from env (`NVIDIA_TIMEOUT_S`, default: `45.0`).
2. Wire it in `apps/agent-worker/src/providers/llm.py`:
   - Extend `build_llm()` to accept a third provider or build a chain like:
     `FallbackAdapter([gemini_primary, nvidia_fallback, open_ai_fallback])`.
   - If `NVIDIA_API_KEY` is absent, skip the NVIDIA adapter and keep `FallbackAdapter([gemini, openai])`.
   - Do **not** make NVIDIA the primary; primary remains Gemini 2.5 Flash.
3. Update `apps/agent-worker/src/config/settings.py`:
   - Add optional settings:
     - `nvidia_api_key: str = "", alias="NVIDIA_API_KEY"`
     - `nvidia_model: str = "meta/llama-3.1-8b-instruct", alias="NVIDIA_MODEL"`
     - `nvidia_timeout_s: float = 45.0, alias="NVIDIA_TIMEOUT_S"`
4. Update root `.env.example`:
   - `NVIDIA_API_KEY=` (fallback)
   - `NVIDIA_MODEL=meta/llama-3.1-8b-instruct`
   - `NVIDIA_TIMEOUT_S=45.0`

### Constraints
- One key only. No rotation, no pool.
- Do not copy the full gateway route logic from the reference code; only the httpx client + response parsing is useful.
- Keep the adapter interface close to `livekit.plugins.openai.LLM(model=...)` so it can be dropped into the fallback list.

---

## 4. Add Groq LLM Adapter

### Required Changes
1. Create a new module `apps/agent-worker/src/providers/groq_adapter.py`:
   - Implement a thin wrapper compatible with the LiveKit `LLM` interface.
   - Use `httpx.AsyncClient` to call Groq's OpenAI-compatible endpoint:
     - Base URL: `https://api.groq.com/openai/v1`
     - Endpoint: `/chat/completions`
     - Auth: `Authorization: Bearer {GROQ_API_KEY}`
   - Support both streaming and non-streaming.
   - Env-configurable model ID: `GROQ_MODEL`, default `llama3-8b-8192` (or current Groq default).
   - Read timeout from env: `GROQ_TIMEOUT_S`, default `30.0`.
2. Wire it in `apps/agent-worker/src/providers/llm.py`:
   - Place it after NVIDIA in the fallback chain.
   - Final chain when all keys are present:
     `FallbackAdapter([gemini_primary, nvidia_fallback, openai_fallback, groq_fallback])`.
   - Skip missing providers gracefully.
3. Update `apps/agent-worker/src/config/settings.py`:
   - `groq_api_key: str = "", alias="GROQ_API_KEY"`
   - `groq_model: str = "llama3-8b-8192", alias="GROQ_MODEL"`
   - `groq_timeout_s: float = 30.0, alias="GROQ_TIMEOUT_S"`
4. Update root `.env.example`:
   - `GROQ_API_KEY=`
   - `GROQ_MODEL=llama3-8b-8192`
   - `GROQ_TIMEOUT_S=30.0`

### Constraints
- Same as NVIDIA: no pool, one key, minimal intrusion.

---

## 5. Configuration & Verification

### .env Variables to Add/Update
Add these entries to the root `.env` and `.env.example` in the existing provider sections:

```bash
# ---- Voice + LLM providers ----
DEEPGRAM_API_KEY=REDACTED_DEEPGRAM_API_KEY         # STT primary & TTS primary/fallback
ELEVEN_API_KEY=                                                    # TTS fallback (ElevenLabs)
AZURE_SPEECH_KEY=                                                  # STT/TTS fallback
AZURE_SPEECH_REGION=francecentral
DEEPGRAM_TTS_MODEL=aura-asteria-en                                   # only if Deepgram TTS model id needed

# ---- LLM chain: Gemini 2.5 Flash primary; GPT via OpenAI, NVIDIA NIM, Groq as fallbacks ----
OPENAI_API_KEY=                                                    # fallback
GOOGLE_API_KEY=GOOGLE_API_KEY_REMOVED  # primary
LLM_PRIMARY_MODEL=gemini-2.5-flash-latest
LLM_FALLBACK_MODEL=gpt-4o-mini

# ---- Optional NVIDIA NIM fallback ----
NVIDIA_API_KEY=
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_TIMEOUT_S=45.0

# ---- Optional Groq fallback ----
GROQ_API_KEY=
GROQ_MODEL=llama3-8b-8192
GROQ_TIMEOUT_S=30.0
```

### Verification Steps
1. Run unit-style import checks:
   ```powershell
   python -c "from providers.llm import build_llm; from config.settings import get_settings; print('LLM builder OK')"
   python -c "from providers.stt import build_stt; from config.language_presets import LANGUAGE_PRESETS; print('STT builder OK')"
   python -c "from providers.tts import build_tts; from config.language_presets import LANGUAGE_PRESETS; print('TTS builder OK')"
   python -c "from providers.nvidia_adapter import NvidiaLLM; print('NVIDIA adapter OK')"
   python -c "from providers.groq_adapter import GroqLLM; print('GROQ adapter OK')"
   ```
2. If possible, run offline tests via `scripts/run_tests.py` and confirm no regressions in agent-worker tests.
3. Update `docs/AI_MODEL_INVENTORY.md` to reflect the new model hierarchy once changes are applied.

---

## 6. File Inventory (affected)

| File | Expected Change |
|---|---|
| `apps/agent-worker/src/config/settings.py` | Swap LLM defaults; add NVIDIA/Groq optional fields; add Deepgram TTS optional fields. |
| `apps/agent-worker/src/config/language_presets.py` | Fix preset keys to include `deepgram_language`, `azure_stt_locale`, `tts_iso`, `azure_tts_voice`. |
| `apps/agent-worker/src/providers/llm.py` | Swap primary/fallback; integrate NVIDIA + Groq adapters into fallback chain. |
| `apps/agent-worker/src/providers/stt.py` | Validate Deepgram primary still works after preset fix; fallback Azure. |
| `apps/agent-worker/src/providers/tts.py` | Reorder to Deepgram primary if supported; keep ElevenLabs/Azure as fallbacks. |
| `apps/agent-worker/src/providers/nvidia_adapter.py` | **NEW** — httpx adapter for NVIDIA NIM. |
| `apps/agent-worker/src/providers/groq_adapter.py` | **NEW** — httpx adapter for Groq. |
| `.env` / `.env.example` | Add/update all model IDs and fallback keys. |
| `docs/AI_MODEL_INVENTORY.md` | Update model hierarchy documentation. |

---

## 7. Important Constraints (read carefully)

- **Do not rewrite the whole agent-worker.** Keep changes localized to `settings.py`, `language_presets.py`, `llm.py`, `stt.py`, `tts.py`, and the two new adapter files.
- **Keep the existing FallbackAdapter pattern.** Each provider layer should return a LiveKit fallback chain.
- **No NVIDIA key pool.** One key, one model.
- **No Groq key pool.** One key, one model.
- **Maintain backward compatibility.** If new env vars are absent, the system must behave as it did before (Gemini/OpenAI fallback after the swap).
- **Arabic STT must remain single-language.** Do not use Deepgram `"multi"` for Arabic; use `language="ar"`.
- **Preserve the chaos/resilience toggles** (`CHAOS_BREAK_STT`, `CHAOS_BREAK_LLM`, `CHAOS_BREAK_TTS`).
- **If Deepgram TTS is unsupported** by the installed LiveKit plugin, clearly document the fallback ordering in code comments and the inventory doc.

---

## 8. Deliverables

When you are done, the following must be true:

1. `python -c "from providers.llm import build_llm; ..."` runs without error and Gemini is primary.
2. `python -c "from providers.stt import build_stt; ..."` runs without `KeyError`.
3. `python -c "from providers.tts import build_tts; ..."` runs without `KeyError`.
4. NVIDIA and Groq adapters import and can be instantiated with an env-provided key.
5. `.env.example` contains all new variables.
6. `docs/AI_MODEL_INVENTORY.md` is updated to match the new configuration.
7. A short summary message lists what changed, what the current primary/fallback order is, and any limitations discovered (e.g., Deepgram TTS plugin availability).




## 1. LLM Model Hierarchy — Gemini 2.5 Flash Primary, GPT Fallback

### 1.1 Context

The platform currently uses a `FallbackAdapter` chain for LLM providers. The current primary is Gemini 2.5 Flash, which has been upgraded to **Gemini 2.5 Flash**. The user has a live Gemini API key with credits. OpenAI GPT is currently the primary but the user has **no OpenAI API key**, so GPT must be moved to a **fallback** position. The existing provider chain in `apps/agent-worker/src/providers/llm.py` reads the model hierarchy from `settings.py` environment variables.

### 1.2 Required Changes

#### A. `apps/agent-worker/src/config/settings.py`

Update or verify the following environment variable names and values:

```python
# Primary LLM — Gemini 2.5 Flash
GEMINI_API_KEY= # User's live Gemini API key — already in .env
GEMINI_MODEL=gemini-2.5-flash   # Updated model ID
GEMINI_ENABLED=true

# Fallback LLM — GPT (no API key currently — keep configured but disabled for now)
OPENAI_API_KEY=   # Empty — no key
OPENAI_MODEL=gpt-4o-mini
OPENAI_ENABLED=false   # Disabled until user adds OpenAI key
```

#### B. `apps/agent-worker/src/providers/llm.py`

Verify the `FallbackAdapter` chain order is:

1. **Primary**: `gemini` — `GEMINI_ENABLED=true`, `GEMINI_API_KEY` set
2. **Fallback**: `openai-gpt` — `OPENAI_ENABLED=true` only when key is present
3. **Additional Fallbacks**: NVIDIA NIM, Groq (added in Section 4–5 below)

Do NOT reorder the internal provider logic — only verify the chain respects the `*_ENABLED` flags and that the settings field names match what the provider reads.

#### C. `.env` / `.env.example`

Confirm these fields exist and are populated:

```env
GEMINI_API_KEY=<user's live key>
GEMINI_MODEL=gemini-2.5-flash
GEMINI_ENABLED=true

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_ENABLED=false
```

---

## 2. STT & TTS — Deepgram Primary with Fallbacks

### 2.1 Context

The platform has STT (Speech-to-Text) and TTS (Text-to-Speech) providers. The user has a **Deepgram API key with credits** and wants Deepgram as the **primary** for both STT and TTS. Azure and ElevenLabs are not yet configured (no API keys) and should remain as **fallback options** that can be enabled later by adding the respective API keys.

The STT builder (`apps/agent-worker/src/providers/stt.py`) and TTS builder (`apps/agent-worker/src/providers/tts.py`) currently read from `LANGUAGE_PRESETS` using keys that **do not exist** in the preset dictionary — this is a confirmed bug (see Section 3).

### 2.2 Required Changes

#### A. `apps/agent-worker/src/config/settings.py` — Verify/Add STT/TTS fields

```python
# STT
DEEPGRAM_STT_API_KEY=<user's live Deepgram STT key — already in .env>
DEEPGRAM_STT_MODEL=nova-2
DEEPGRAM_STT_ENABLED=true

AZURE_STT_API_KEY=
AZURE_STT_REGION=westeurope
AZURE_STT_ENABLED=false   # No key — disabled

# TTS
DEEPGRAM_TTS_API_KEY=<same Deepgram key — or separate TTS key>
DEEPGRAM_TTS_MODEL=aura-2-hex
DEEPGRAM_TTS_ENABLED=true

ELEVENLABS_API_KEY=
ELEVENLABS_MODEL=eleven_flash_v2_5
ELEVENLABS_ENABLED=false   # No key — disabled

AZURE_TTS_API_KEY=
AZURE_TTS_REGION=westeurope
AZURE_TTS_ENABLED=false   # No key — disabled
```

#### B. `apps/agent-worker/src/providers/stt.py` — Verify Deepgram primary

Confirm the builder reads:
- Primary: `deepgram.STT(language=preset["deepgram_language"])`
- Fallback: `azure.STT(language=preset["azure_stt_locale"])`

And that `deepgram_language` key exists in `LANGUAGE_PRESETS` after the fix in Section 3.

#### C. `apps/agent-worker/src/providers/tts.py` — Verify Deepgram primary

Confirm the builder reads:
- Primary: `elevenlabs.TTS(language=preset["tts_iso"])` **OR** `deepgram.TTS` depending on preference
- Fallback: `azure.TTS(voice=preset["azure_tts_voice"])`

**Note**: The user prefers Deepgram as primary for TTS. If Deepgram TTS uses a different API key than STT, ensure both keys are read from `.env`. If Deepgram TTS is not available as a separate product, use ElevenLabs as primary TTS and Deepgram as secondary fallback. Verify the actual Deepgram TTS offering and adjust accordingly.

#### D. `.env` / `.env.example` — Confirm Deepgram STT key

```env
DEEPGRAM_API_KEY=<user's live Deepgram key>
DEEPGRAM_STT_API_KEY=<same key or separate STT-specific key>
DEEPGRAM_TTS_API_KEY=<same key or separate TTS-specific key>
```

---

## 3. LANGUAGE_PRESETS Bug Fix — Critical

### 3.1 The Bug

`apps/agent-worker/src/config/language_presets.py` defines per-language presets with incorrect key names. The STT and TTS builders in `stt.py:18` and `tts.py:18` try to read keys that **do not exist** in the preset dictionary, causing a `KeyError` at runtime.

**Current preset structure (BROKEN)**:

```python
LANGUAGE_PRESETS = {
    "en": {
        "stt_language": "en-US",   # ← Builder reads "deepgram_language" ❌
        "tts_voice": "en-US-JennyMultilingualNeural",  # ← Builder reads "azure_tts_voice" ❌
    },
    "fr": { ... },
    "ar": { ... },
    "es": { ... },
}
```

**What the builders actually read**:

```python
# stt.py — primary Deepgram
language=preset["deepgram_language"]   # ❌ KeyError — key doesn't exist

# stt.py — fallback Azure
language=preset["azure_stt_locale"]    # ❌ KeyError — key doesn't exist

# tts.py — primary ElevenLabs (or Deepgram TTS)
language=preset["tts_iso"]              # ❌ KeyError — key doesn't exist

# tts.py — fallback Azure
voice=preset["azure_tts_voice"]        # ❌ KeyError — key doesn't exist
```

### 3.2 Required Fix

Rewrite `apps/agent-worker/src/config/language_presets.py` so each language preset contains **all four keys** the builders read:

```python
LANGUAGE_PRESETS = {
    "en": {
        # STT — Deepgram
        "deepgram_language": "en-US",
        # STT — Azure fallback
        "azure_stt_locale": "en-US",
        # TTS — ElevenLabs / Deepgram TTS
        "tts_iso": "en",
        # TTS — Azure fallback
        "azure_tts_voice": "en-US-JennyMultilingualNeural",
    },
    "fr": {
        "deepgram_language": "fr-FR",
        "azure_stt_locale": "fr-FR",
        "tts_iso": "fr",
        "azure_tts_voice": "fr-FR-DeniseNeural",
    },
    "ar": {
        "deepgram_language": "ar-SA",
        "azure_stt_locale": "ar-SA",
        "tts_iso": "ar",
        "azure_tts_voice": "ar-SA-NaayfNeural",
    },
    "es": {
        "deepgram_language": "es-ES",
        "azure_stt_locale": "es-ES",
        "tts_iso": "es",
        "azure_tts_voice": "es-ES-ElviraNeural",
    },
}
```

### 3.3 After the Fix

Verify that after rewriting the preset:
- `stt.py` can call `preset["deepgram_language"]` and `preset["azure_stt_locale"]` without error
- `tts.py` can call `preset["tts_iso"]` and `preset["azure_tts_voice"]` without error
- All 4 supported languages (en, fr, ar, es) have all 4 keys
- The correct language codes are used for each provider (e.g., Deepgram uses `en-US`, `fr-FR`, `ar-SA`, `es-ES` — verify these are valid Deepgram language codes)

---

## 4. NVIDIA NIM Adapter — Add as Fallback LLM

### 4.1 Context

The user has NVIDIA API keys with free credits and generous quotas. A new NVIDIA NIM adapter must be added as a **fallback LLM** (secondary after GPT, before any local model fallback). The adapter should be a **single-key implementation** (not a key pool — the pool concept from the user's previous project is not needed here).

The adapter must integrate seamlessly with the existing `FallbackAdapter` chain and use the same `BaseProvider` interface (`CompletionRequest`, `CompletionResponse`, `Message`, `TokenUsage`) that other providers (`gemini`, `openai`) already use.

### 4.2 Design Constraints

- **Single key**: Use one `NVIDIA_API_KEY` from `.env` — no key rotation or pooling
- **Interface**: Must implement the existing `BaseProvider` contract so it drops into the `FallbackAdapter` chain without any changes to existing provider logic
- **API endpoint**: `https://integrate.api.nvidia.com/v1` (NVIDIA NIM endpoint)
- **Model**: Configurable via `NVIDIA_MODEL` env var (e.g., `meta/llama-3.1-8b-instruct`)
- **Streaming**: Must support the `stream()` method for streaming responses
- **No pool logic**: Do not implement `NvidiaKeyPool` or any multi-key rotation logic — just one key
- **Error handling**: On HTTP errors (429, 5xx, timeout), raise/surface the error so the `FallbackAdapter` can rotate to the next provider

### 4.3 Required Files to Create

#### A. `apps/agent-worker/src/providers/nvidia_adapter.py`

```python
"""
NVIDIA NIM Adapter — Fallback LLM Provider.

Implements the BaseProvider interface.
Configured via NVIDIA_API_KEY + NVIDIA_MODEL env vars.
"""
from __future__ import annotations

import time
from typing import AsyncIterator

import httpx

from providers.base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    TokenUsage,
)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
_REQUEST_TIMEOUT_S = 60.0


class NvidiaAdapter(BaseProvider):
    """
    Single-key NVIDIA NIM adapter.
    Drops into FallbackAdapter chain — no pool, no rotation.
    """
    name = "nvidia-nim"

    def __init__(self, api_key: str, model: str, timeout: float = _REQUEST_TIMEOUT_S):
        self._api_key = api_key
        self._model   = model
        self._timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

    def _payload(self, req: CompletionRequest, stream: bool) -> dict:
        p: dict = {
            "model":             self._model,
            "messages":          [{"role": m.role, "content": m.content} for m in req.messages],
            "max_tokens":        req.max_tokens,
            "temperature":       req.temperature,
            "top_p":             req.top_p,
            "frequency_penalty": req.frequency_penalty,
            "presence_penalty":  req.presence_penalty,
            "stream":            stream,
        }
        if req.response_format:
            p["response_format"] = req.response_format
        return p

    async def complete(self, req: CompletionRequest) -> CompletionResponse:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers=self._headers(),
                json=self._payload(req, stream=False),
            )
        resp.raise_for_status()
        latency = int((time.perf_counter() - t0) * 1000)
        data    = resp.json()
        choice  = data["choices"][0]
        usage   = data.get("usage", {})

        return CompletionResponse(
            content=choice["message"]["content"],
            provider=self.name,
            model=self._model,
            usage=TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            latency_ms=latency,
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        import json as _json
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers={**self._headers(), "Accept": "text/event-stream"},
                json=self._payload(req, stream=True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        return
                    try:
                        chunk  = _json.loads(raw)
                        delta  = (
                            chunk["choices"][0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{NVIDIA_BASE_URL}/models",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False
```

#### B. `apps/agent-worker/src/config/settings.py` — Add NVIDIA fields

```python
# NVIDIA NIM (fallback LLM — single key, no pool)
nvidia_api_key: str = ""
nvidia_model: str = "meta/llama-3.1-8b-instruct"
nvidia_timeout_s: float = 60.0
nvidia_enabled: bool = False   # Disabled until user adds key
```

#### C. `apps/agent-worker/src/providers/llm.py` — Wire NVIDIA into the chain

Add NVIDIA as a provider in the `FallbackAdapter` chain at the appropriate position:
1. Primary: `gemini` (ENABLED)
2. Fallback 1: `openai-gpt` (ENABLED only when key present)
3. Fallback 2: `nvidia-nim` (ENABLED when key added)
4. Fallback 3: `groq` (added in Section 5)
5. Final fallback: local model or graceful error

Do NOT change the internal logic of existing providers — only add the NVIDIA adapter to the chain and ensure it is instantiated with the correct env var values.

#### D. `.env` / `.env.example` — Add NVIDIA fields

```env
NVIDIA_API_KEY=<user will add their NVIDIA API key here>
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_ENABLED=false   # Set to true when key is added
```

---

## 5. Groq Adapter — Add as Fallback LLM

### 5.1 Context

Groq provides free API keys with generous quotas. Add Groq as another fallback LLM provider, positioned after GPT and NVIDIA NIM in the chain. Implement the same `BaseProvider` interface for seamless integration.

### 5.2 Design Constraints

- **Single key**: Use one `GROQ_API_KEY` from `.env`
- **Interface**: Implement `BaseProvider` — `complete()`, `stream()`, `health_check()`, `is_available`
- **API endpoint**: `https://api.groq.com/openai/v1`
- **Model**: Configurable via `GROQ_MODEL` env var (e.g., `llama-3.1-8b` or `mixtral-8x7b`)
- **Streaming**: Must support the `stream()` method
- **Error handling**: Surface errors so `FallbackAdapter` can rotate to next provider

### 5.3 Required Files to Create

#### A. `apps/agent-worker/src/providers/groq_adapter.py`

```python
"""
Groq Adapter — Fallback LLM Provider.

Implements the BaseProvider interface.
Configured via GROQ_API_KEY + GROQ_MODEL env vars.
"""
from __future__ import annotations

import time
from typing import AsyncIterator

import httpx

from providers.base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_REQUEST_TIMEOUT_S = 45.0


class GroqAdapter(BaseProvider):
    """
    Single-key Groq adapter.
    Drops into FallbackAdapter chain.
    """
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout: float = _REQUEST_TIMEOUT_S):
        self._api_key = api_key
        self._model   = model
        self._timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

    def _payload(self, req: CompletionRequest, stream: bool) -> dict:
        p: dict = {
            "model":             self._model,
            "messages":          [{"role": m.role, "content": m.content} for m in req.messages],
            "max_tokens":        req.max_tokens,
            "temperature":       req.temperature,
            "top_p":             req.top_p,
            "frequency_penalty": req.frequency_penalty,
            "presence_penalty":  req.presence_penalty,
            "stream":            stream,
        }
        if req.response_format:
            p["response_format"] = req.response_format
        return p

    async def complete(self, req: CompletionRequest) -> CompletionResponse:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers=self._headers(),
                json=self._payload(req, stream=False),
            )
        resp.raise_for_status()
        latency = int((time.perf_counter() - t0) * 1000)
        data    = resp.json()
        choice  = data["choices"][0]
        usage   = data.get("usage", {})

        return CompletionResponse(
            content=choice["message"]["content"],
            provider=self.name,
            model=self._model,
            usage=TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            latency_ms=latency,
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        import json as _json
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{GROQ_BASE_URL}/chat/completions",
                headers={**self._headers(), "Accept": "text/event-stream"},
                json=self._payload(req, stream=True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        return
                    try:
                        chunk  = _json.loads(raw)
                        delta  = (
                            chunk["choices"][0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{GROQ_BASE_URL}/models",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False
```

#### B. `apps/agent-worker/src/config/settings.py` — Add Groq fields

```python
# Groq (fallback LLM — single key)
groq_api_key: str = ""
groq_model: str = "llama-3.1-8b-instant"
groq_timeout_s: float = 45.0
groq_enabled: bool = False   # Disabled until user adds key
```

#### C. `apps/agent-worker/src/providers/llm.py` — Wire Groq into the chain

Add Groq after NVIDIA NIM in the `FallbackAdapter` chain.

#### D. `.env` / `.env.example` — Add Groq fields

```env
GROQ_API_KEY=<user will add their Groq API key here>
GROQ_MODEL=llama-3.1-8b-instant
GROQ_ENABLED=false   # Set to true when key is added
```

---

## 6. Verify `.env` Credentials are Correctly Loaded at Startup

### 6.1 Context

All API keys and configuration must be read from the root `.env` file and correctly passed to each provider at startup. The `settings.py` uses `pydantic_settings.BaseSettings` with `env_file=".env"` to load these values.

### 6.2 Required Verification

Run through each service's startup and confirm:

1. **Agent Worker** (`apps/agent-worker`): Loads `GEMINI_API_KEY`, `DEEPGRAM_API_KEY`, `NVIDIA_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY` from `.env` correctly
2. **LLM Service** (`services/llm-service`): Loads NVIDIA config (if used as standalone service)
3. **All providers** (`stt.py`, `tts.py`, `llm.py`): Read their respective API keys from `settings.py`, which pulls from `.env`

### 6.3 Credentials Summary

| Provider | Env Var | Status |
|---|---|---|
| Gemini 2.5 Flash | `GEMINI_API_KEY` | **Live key present** |
| OpenAI GPT | `OPENAI_API_KEY` | Empty — no key |
| Deepgram STT | `DEEPGRAM_API_KEY` | **Live key present** |
| Deepgram TTS | `DEEPGRAM_API_KEY` | Same key (or separate) |
| Azure STT | `AZURE_STT_API_KEY` | Empty — not configured |
| ElevenLabs TTS | `ELEVENLABS_API_KEY` | Empty — not configured |
| Azure TTS | `AZURE_TTS_API_KEY` | Empty — not configured |
| NVIDIA NIM | `NVIDIA_API_KEY` | User will add |
| Groq | `GROQ_API_KEY` | User will add |

---

## 7. Final LLM Provider Chain Order

After all changes, the `FallbackAdapter` LLM chain must be ordered as follows:

```
1. gemini-2.5-flash     [PRIMARY]  — GEMINI_ENABLED=true, key set
2. openai-gpt-4o-mini    [FALLBACK] — OPENAI_ENABLED=true only when key added
3. nvidia-nim           [FALLBACK] — NVIDIA_ENABLED=true when key added
4. groq                 [FALLBACK] — GROQ_ENABLED=true when key added
5. graceful error / local model fallback
```

---

## 8. STT/TTS Provider Chain Order

After all changes:

**STT**:
```
1. deepgram-nova-2   [PRIMARY]  — DEEPGRAM_STT_ENABLED=true, key set
2. azure-stt         [FALLBACK] — AZURE_STT_ENABLED=true only when key added
```

**TTS**:
```
1. deepgram-tts / elevenlabs  [PRIMARY]  — DEEPGRAM_TTS_ENABLED=true (or ELEVENLABS_ENABLED=true)
2. azure-tts                  [FALLBACK] — AZURE_TTS_ENABLED=true only when key added
```

---

## 9. Validation Checklist

After applying all changes, verify:

- [ ] `gemini-2.5-flash` is the active primary LLM
- [ ] `OPENAI_API_KEY` is empty and `OPENAI_ENABLED=false` in `.env`
- [ ] `LANGUAGE_PRESETS` contains all 4 keys per language: `deepgram_language`, `azure_stt_locale`, `tts_iso`, `azure_tts_voice`
- [ ] STT builder (`stt.py`) can read `preset["deepgram_language"]` and `preset["azure_stt_locale"]` without `KeyError`
- [ ] TTS builder (`tts.py`) can read `preset["tts_iso"]` and `preset["azure_tts_voice"]` without `KeyError`
- [ ] `DEEPGRAM_API_KEY` is present in `.env` and loaded correctly
- [ ] Deepgram is primary for both STT and TTS
- [ ] `nvidia_adapter.py` is created and implements `BaseProvider` correctly
- [ ] `groq_adapter.py` is created and implements `BaseProvider` correctly
- [ ] Both adapters are wired into `llm.py` `FallbackAdapter` chain
- [ ] `NVIDIA_API_KEY` and `GROQ_API_KEY` fields exist in `.env` (empty, ready to be filled)
- [ ] No existing provider logic or agent behavior was changed — only configuration and new adapter files
- [ ] All Python files compile without import errors
- [ ] All TOML/INI files parse correctly

---

## 10. Files Reference

### Existing files (read, do not rewrite):
- `apps/agent-worker/src/config/settings.py` — Add NVIDIA, Groq, Deepgram STT/TTS env fields
- `apps/agent-worker/src/config/language_presets.py` — Rewrite with correct 4 keys per language
- `apps/agent-worker/src/providers/llm.py` — Wire NVIDIA and Groq into FallbackAdapter chain
- `apps/agent-worker/src/providers/stt.py` — Verify Deepgram primary, keep as-is
- `apps/agent-worker/src/providers/tts.py` — Verify Deepgram primary, keep as-is
- `.env` — Add `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `NVIDIA_ENABLED`, `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_ENABLED`, `DEEPGRAM_STT/TTS` keys
- `.env.example` — Same additions

### New files to create:
- `apps/agent-worker/src/providers/nvidia_adapter.py`
- `apps/agent-worker/src/providers/groq_adapter.py`

### Do NOT modify:
- Existing provider internal logic (gemini, openai, azure, elevenlabs)
- Agent behavior or business logic
- `service_auth` or inter-service authentication
- Infrastructure code (docker-compose, helm, nginx)
- CI/CD pipeline