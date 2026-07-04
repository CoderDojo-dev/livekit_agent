# Telecom AI Voice Agent Platform — Source Code Reference

> **Code Layout**: Each section lists the file path, then the complete source code.

---

## Table of Contents

1. [Root Configuration](#1-root-configuration)
2. [Agent Worker — Configuration](#2-agent-worker--configuration)
3. [Agent Worker — Providers (STT/TTS/LLM/VAD)](#3-agent-worker--providers)
4. [Agent Worker — Composition Root & Agents](#4-agent-worker--composition-root--agents)
5. [Agent Worker — Tools & Guards](#5-agent-worker--tools--guards)
6. [Agent Worker — Domain Clients](#6-agent-worker--domain-clients)
7. [Agent Worker — Session, Sentiment, Conversation](#7-agent-worker--session-sentiment-conversation)
8. [Agent Worker — Observability & MCP Clients](#8-agent-worker--observability--mcp-clients)
9. [Agent Worker — Tasks & Entrypoints](#9-agent-worker--tasks--entrypoints)
10. [Service Auth Package](#10-service-auth-package)
11. [Docker & Container Files](#11-docker--container-files)
12. [Other Agents](#12-other-agents)

---

## 1. Root Configuration

### .env

```env
# =============================================================================
# Telecom AI Voice Agent — local development environment
# Every variable below is read by at least one module in the project.
# Unset = safe default for dev (unless marked ⚠).
# Copy to deploy/secrets/.env and fill in live credentials for staging/prod.
# =============================================================================

# ===================================================================
# 1. DATABASE
# ===================================================================
DATABASE_URL=postgresql+psycopg://telecom:telecom@localhost:5432/telecom
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30.0
DB_POOL_RECYCLE=1800
POSTGRES_USER=telecom
POSTGRES_PASSWORD=telecom
POSTGRES_DB=telecom

# ===================================================================
# 2. ADAPTER MODE
# ===================================================================
CONNECTOR_MODE=live                     # mock | live

# ===================================================================
# 3. SERVICE-TO-SERVICE AUTH
# ===================================================================
INTERNAL_API_KEY=                       # unset = disabled (dev)

# ===================================================================
# 4. EDGE / CORS
# ===================================================================
CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# ===================================================================
# 5. LIVEKIT (transport)
# ===================================================================
LIVEKIT_URL=wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud
LIVEKIT_API_KEY=API4oF2JZPKv5s7
LIVEKIT_API_SECRET=K2vSLuHfjm5Psu95A7yuXUVnqGMR2qlWl1O6p0niSYE

# ===================================================================
# 6. VOICE + LLM PROVIDERS
# ===================================================================
# --- STT primary (Deepgram has live key with credits) ---
DEEPGRAM_API_KEY=5b6fe60c9247547af783599f56

# --- TTS primary (ElevenLabs) | fallback providers ---
ELEVEN_API_KEY=                         # EMPTY — TTS primary non-functional
CARTESIA_API_KEY=sk_car_tofNa8mAPgQWd7uVqEiQom
AZURE_SPEECH_KEY=                       # EMPTY — final fallback
AZURE_SPEECH_REGION=francecentral

# --- LLM primary (Gemini 2.5 Flash — live key) ---
GOOGLE_API_KEY=REDACTED_GOOGLE_API_KEY

# --- LLM fallbacks ---
OPENAI_API_KEY=sk-proj-yfxOac6VXbzJ5B479sbQpc5xvyiVEGPX5mR1X9fQ4x25BlbkFJ-bL8J3M-e0Gu6SAoHwnfPvD6Snxgz0xeZ-JOwJHA5ozxroBDERAcHEPYZZny56SVQfk
NVIDIA_API_KEY=nvapi-xq04a5nm6KdPoQ6pjuIMlGnCxGXr0iFC0Wivr4elmfoJM8yqHgk
GROQ_API_KEY=gsk_BTE4b9zhpYE5VmU3wm5MWGdyb3FYz7llafVgaO5xX

# --- STT optional extra fallback ---
GLADIA_API_KEY=a7a21c8a-27b7-4095-81db-35125c4

# ===================================================================
# 7. MODEL SELECTION
# ===================================================================
STT_MODEL=nova-3
TTS_MODEL=eleven_flash_v2_5
ELEVEN_VOICE_ID=EXAVITQu4vr4xnSDxMaL
DEEPGRAM_TTS_MODEL=aura-asteria-en
DEEPGRAM_TTS_VOICE=aura-asteria-en

LLM_PRIMARY_MODEL=gemini-2.5-flash-latest                          # ⚠ Should be gemini-3.5-flash
LLM_FALLBACK_MODEL=gpt-4o-mini
NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b
NVIDIA_TIMEOUT_S=45.0
GROQ_MODEL=llama3-8b-8192                                           # ⚠ Decommissioned by Groq
GROQ_TIMEOUT_S=30.0
CARTESIA_TTS_MODEL=sonic-2

# ===================================================================
# 8. VAD / TURN / LATENCY
# ===================================================================
VAD_MIN_SILENCE=0.25
PREEMPTIVE_GENERATION=True
NOISE_CANCELLATION=False
DECISION_CONFIDENCE_THRESHOLD=0.5

# ===================================================================
# 9. CHAOS / RESILIENCE
# ===================================================================
CHAOS_BREAK_STT=False
CHAOS_BREAK_LLM=False
CHAOS_BREAK_TTS=False

# ===================================================================
# 10. LANGUAGE / SESSION
# ===================================================================
SUPPORTED_LANGUAGES=fr,ar,en
DEFAULT_LANGUAGE=fr
SESSION_LANGUAGE=fr
SESSION_CALLER_MSISDN=

# ===================================================================
# 11. DOMAIN SERVICE URLs
# ===================================================================
CONTEXT_SERVICE_URL=http://localhost:8101
KNOWLEDGE_SERVICE_URL=http://localhost:8102
DECISION_SERVICE_URL=http://localhost:8103
POLICY_SERVICE_URL=http://localhost:8104
EXECUTION_SERVICE_URL=http://localhost:8105
NOTIFICATION_SERVICE_URL=http://localhost:8106

# ===================================================================
# 12. MCP SERVER URLs
# ===================================================================
KNOWLEDGE_MCP_URL=http://localhost:8201/mcp
TICKETING_MCP_URL=http://localhost:8202/mcp
MESSAGING_MCP_URL=http://localhost:8203/mcp

# ===================================================================
# 13. MCP SERVER HOST/PORT
# ===================================================================
MCP_HOST=0.0.0.0

# ===================================================================
# 14. GLPI TICKETING (live)
# ===================================================================
GLPI_BASE_URL=https://voiceagentai.fr33.glpi-network.cloud/api.php/v1
GLPI_APP_TOKEN=gwwC5gJCv3ovxU1BxVN2c4unNoKKZBUwzl
GLPI_USER_TOKEN=6fE8nsdoloRNC5AgnbcIlow8uU6NkrX4ki

# ===================================================================
# 15. MESSAGING / NOTIFICATION
# ===================================================================
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_SMS_FROM=
TWILIO_WHATSAPP_FROM=
SENDGRID_API_KEY=
EMAIL_FROM=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# ===================================================================
# 16. LEGACY SYSTEM ADAPTER URLs
# ===================================================================
OCS_ADAPTER_URL=
BILLING_ADAPTER_URL=
PAYMENT_ADAPTER_URL=
CRM_ADAPTER_URL=
NMS_ADAPTER_URL=
PROVISIONING_ADAPTER_URL=
GLPI_ADAPTER_URL=

# ===================================================================
# 17. KNOWLEDGE / RAG (Qdrant)
# ===================================================================
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=telecom_knowledge
EMBEDDING_MODEL=text-embedding-3-small

# ===================================================================
# 18. CACHE (Redis)
# ===================================================================
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300

# ===================================================================
# 19. OBJECT STORAGE (MinIO)
# ===================================================================
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=call-recordings
MINIO_SECURE=false

# ===================================================================
# 20. OBSERVABILITY
# ===================================================================
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=telecom-agent

# ===================================================================
# 21. POLICY SERVICE THRESHOLDS
# ===================================================================
POLICY_PAYMENT_CAP_TND=200.0
POLICY_DEFERRAL_MIN_AGE_DAYS=180
POLICY_DEFERRAL_MAX_PER_YEAR=2
POLICY_DEFERRAL_UNPAID_THRESHOLD_TND=150.0

# ===================================================================
# 22. BUSINESS API
# ===================================================================
BUSINESS_API_DEFAULT_ROLE=administrateur

# ===================================================================
# 23. BACKUP
# ===================================================================
BACKUP_DIR=./backups

# ===================================================================
# 24. LOGGING
# ===================================================================
LOG_LEVEL=INFO

# ===================================================================
# 25. FRONTENDS (Vite)
# ===================================================================
VITE_TOKEN_URL=http://localhost:8107
VITE_BUSINESS_API_URL=http://localhost:8108
VITE_API_ROLE=administrateur
```

### Makefile

```makefile
# Telecom AI Voice Agent — one place to install, run, verify.
SHELL := /bin/bash
PACKAGES := domain-core persistence audit-trail pii-shield observability-kit service-auth cache object-storage notification-client integration-adapters
SERVICES := services/context-service services/knowledge-service services/decision-service services/policy-service services/execution-service services/notification-service apps/token-service apps/business-api
MCP := mcp-servers/ai-knowledge-rag mcp-servers/ticketing-glpi mcp-servers/messaging-gateway
INFRA := infra/docker-compose/docker-compose.yml
APPS := infra/docker-compose/docker-compose.apps.yml
export DATABASE_URL ?= postgresql+psycopg://telecom:telecom@localhost:5432/telecom
PYTHON := "$(shell if [ -x .venv/bin/python ]; then echo $(CURDIR)/.venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo $(CURDIR)/.venv/Scripts/python.exe; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)"
PIP := $(PYTHON) -m pip
UVICORN := $(PYTHON) -m uvicorn
HONCHO := $(shell if [ -x .venv/bin/honcho ]; then echo $(CURDIR)/.venv/bin/honcho; elif [ -x .venv/Scripts/honcho.exe ]; then echo $(CURDIR)/.venv/Scripts/honcho.exe; else echo honcho; fi)

.DEFAULT_GOAL := help
.PHONY: help install infra infra-livekit create-db migrate seed dev up down rebuild health live-logs test frontends frontends-clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Install all packages + services + MCP + honcho (editable)
	$(PIP) install honcho
	$(PIP) install $(addprefix -e ./packages/,$(PACKAGES))
	$(PIP) install $(addprefix -e ./,$(SERVICES)) $(addprefix -e ./,$(MCP)) -e ./apps/agent-worker
	@echo "→ frontends: run 'make frontends'"

frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS
	cd apps/supervisor-dashboard && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install

infra:  ## Start infrastructure containers (postgres/redis/qdrant/minio/otel)
	docker compose -f $(INFRA) up -d

infra-livekit:  ## Also start the self-hosted LiveKit server
	docker compose -f $(INFRA) --profile self-hosted-livekit up -d

create-db:  ## Create the telecom database in Postgres if it does not exist yet
	docker compose -f $(INFRA) exec -T postgres psql -U "$${POSTGRES_USER:-telecom}" -d postgres -c "CREATE DATABASE \"$${POSTGRES_DB:-telecom}\" OWNER \"$${POSTGRES_USER:-telecom}\";" 2>/dev/null || true

migrate: create-db  ## Apply DB migrations (alembic upgrade head)
	cd packages/persistence && $(PYTHON) -m alembic upgrade head

seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference

dev: install infra migrate seed  ## ONE COMMAND: install + infra + migrate + seed, then run everything
	@echo "Starting all app processes via honcho (Ctrl-C to stop all)…"
	$(HONCHO) start

up:  ## Full container path: infra + every app service via compose (builds images)
	docker compose -f $(INFRA) -f $(APPS) up -d --build

down:  ## Stop everything (infra + apps + optional livekit)
	docker compose -f $(INFRA) -f $(APPS) --profile self-hosted-livekit down

rebuild: down  ## Stop + rebuild + redeploy all containers (use after code changes)
	docker compose -f $(INFRA) -f $(APPS) up -d --build
	@echo "→ All images rebuilt & containers running. Run 'make health' to verify."

health:  ## Probe every service /health
	$(PYTHON) scripts/health_check.py

live-logs:  ## Follow token-service + agent-worker logs during a browser call
	docker compose -f $(INFRA) -f $(APPS) logs -f --tail=120 token-service agent-worker

test:  ## Run the offline test suite across packages/services
	$(PYTHON) scripts/run_tests.py
```

### Procfile

```text
# honcho/foreman process list
context:       context-service
knowledge:     knowledge-service
decision:      decision-service
policy:        policy-service
execution:     execution-service
notification:  notification-service
token:         token-service
business:      business-api
knowledge-mcp: ai-knowledge-rag
ticketing-mcp: ticketing-glpi
messaging-mcp: messaging-gateway
worker:        python apps/agent-worker/src/server.py start
dashboard:     npm --prefix apps/supervisor-dashboard run dev
widget:        npm --prefix apps/client-widget run dev
```

---

## 2. Agent Worker — Configuration

### `apps/agent-worker/pyproject.toml`

```toml
[project]
name = "agent-worker"
version = "0.1.0"
description = "LiveKit Agents real-time orchestrator. Thin tools; zero business logic."
requires-python = ">=3.12"
dependencies = [
  "object-storage",
  "service-auth",
  "audit-trail",
  "persistence",
  "livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia]==1.6.3",
  "mcp>=1.12,<2",
  "pydantic==2.10.4",
  "pydantic-settings==2.7.1",
  "httpx==0.28.1",
  "structlog==24.4.0",
  "python-dotenv==1.0.1",
  "domain-core",
  "observability-kit",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### `apps/agent-worker/src/config/settings.py`

```python
"""Twelve-Factor settings: everything via environment, nothing hardcoded.

This module holds configuration values only. It imports no vendor plugin: provider
construction (including noise cancellation) lives behind the providers/ boundary.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- LiveKit transport (self-hosted) ---
    livekit_url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("devsecret_change_me", alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("telecom-agent", alias="LIVEKIT_AGENT_NAME")

    # --- Language scope / spike session language ---
    supported_languages: str = Field("fr,ar,en", alias="SUPPORTED_LANGUAGES")
    default_language: str = Field("fr", alias="DEFAULT_LANGUAGE")
    session_language: str = Field("fr", alias="SESSION_LANGUAGE")
    session_caller_msisdn: str = Field("", alias="SESSION_CALLER_MSISDN")

    # --- STT primary (Deepgram) ---
    stt_model: str = Field("nova-3", alias="STT_MODEL")

    # --- TTS primary (ElevenLabs Flash v2.5) ---
    tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")

    # --- Deepgram TTS (optional — if livekit-plugins-deepgram adds TTS support) ---
    deepgram_tts_model: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_MODEL")
    deepgram_tts_voice: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_VOICE")

    # --- LLM chain: Gemini 2.5 Flash primary, OpenAI GPT-4o-mini fallback ---
    llm_primary_model: str = Field("gemini-2.5-flash-latest", alias="LLM_PRIMARY_MODEL")       # ⚠ SHOULD BE gemini-3.5-flash
    llm_fallback_model: str = Field("gpt-4o-mini", alias="LLM_FALLBACK_MODEL")

    # --- Optional NVIDIA NIM fallback LLM (single key, no pool) ---
    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-8b-instruct", alias="NVIDIA_MODEL")
    nvidia_timeout_s: float = Field(45.0, alias="NVIDIA_TIMEOUT_S")

    # --- Optional Groq fallback LLM (single key, no pool) ---
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama3-8b-8192", alias="GROQ_MODEL")                              # ⚠ DECOMMISSIONED — use llama-3.1-8b-instant
    groq_timeout_s: float = Field(30.0, alias="GROQ_TIMEOUT_S")

    # --- Optional Gladia STT (additional fallback after Azure) ---
    gladia_api_key: str = Field("", alias="GLADIA_API_KEY")

    # --- Optional Cartesia TTS (additional TTS option behind ElevenLabs) ---
    cartesia_api_key: str = Field("", alias="CARTESIA_API_KEY")
    cartesia_tts_model: str = Field("sonic-2", alias="CARTESIA_TTS_MODEL")

    # --- VAD / turn detection / latency ---
    vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")
    preemptive_generation: bool = Field(True, alias="PREEMPTIVE_GENERATION")
    noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")

    # --- Decision -> Policy façade ---
    decision_confidence_threshold: float = Field(0.5, alias="DECISION_CONFIDENCE_THRESHOLD")

    # --- Resilience chaos toggles (cookbook section 16): break a primary on purpose ---
    chaos_break_stt: bool = Field(False, alias="CHAOS_BREAK_STT")
    chaos_break_llm: bool = Field(False, alias="CHAOS_BREAK_LLM")
    chaos_break_tts: bool = Field(False, alias="CHAOS_BREAK_TTS")

    # --- Domain service URLs ---
    context_service_url: str = Field("http://localhost:8101", alias="CONTEXT_SERVICE_URL")
    decision_service_url: str = Field("http://localhost:8103", alias="DECISION_SERVICE_URL")
    policy_service_url: str = Field("http://localhost:8104", alias="POLICY_SERVICE_URL")
    execution_service_url: str = Field("http://localhost:8105", alias="EXECUTION_SERVICE_URL")
    notification_service_url: str = Field("http://localhost:8106", alias="NOTIFICATION_SERVICE_URL")
    knowledge_mcp_url: str = Field("http://localhost:8201/mcp", alias="KNOWLEDGE_MCP_URL")
    ticketing_mcp_url: str = Field("http://localhost:8202/mcp", alias="TICKETING_MCP_URL")

    @property
    def languages(self) -> list[str]:
        """Parsed supported-language list."""
        return [item.strip() for item in self.supported_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
```

### `apps/agent-worker/src/config/language_presets.py`

```python
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

LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
    "fr": {
        "deepgram_language": "fr",
        "azure_stt_locale": "fr-FR",
        "gladia_language": "fr",
        "tts_iso": "fr",
        "azure_tts_voice": "fr-FR-DeniseNeural",
        "cartesia_voice_id": "a249eaff-1e96-4d2c-b23b-12efa4c2d4b1",
    },
    "ar": {
        "deepgram_language": "ar",
        "azure_stt_locale": "ar-EG",
        "gladia_language": "ar",
        "tts_iso": "ar",
        "azure_tts_voice": "ar-EG-SalmaNeural",
        "cartesia_voice_id": "79743797-2087-422f-8e74-6d2b03ae5b31",
    },
    "en": {
        "deepgram_language": "en",
        "azure_stt_locale": "en-US",
        "gladia_language": "en",
        "tts_iso": "en",
        "azure_tts_voice": "en-US-JennyNeural",
        "cartesia_voice_id": "694f9389-aac1-45b6-b726-9d9369183238",
    },
}

GREETINGS: dict[str, str] = {
    "fr": "Saluez brièvement l'appelant en français et demandez comment vous pouvez l'aider aujourd'hui.",
    "ar": "حي المتصل باختصار باللغة العربية واسأله كيف يمكنك مساعدته اليوم.",
    "en": "Briefly greet the caller in English and ask how you can help today.",
}
```

---

## 3. Agent Worker — Providers

### `apps/agent-worker/src/providers/session_factory.py`

```python
"""Thin session assembler (cookbook section 4/5, SRP-refined).

This file contains NO vendor-plugin import. It composes the per-concern builders from the
providers/ package into one AgentSession. Vendor coupling lives only in the builder modules
(stt/tts/llm/vad) and the isolated turn_detection wrapper — the providers/ package is the
single vendor boundary, enforceable by a lint rule: no `livekit.plugins` import may appear
outside apps/agent-worker/src/providers/.
"""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from livekit.agents import AgentSession

from providers.llm import build_llm
from providers.stt import build_stt
from providers.tts import build_tts
from providers.turn_detection import build_turn_detector
from providers.vad import build_vad


def build_agent_session(settings: Settings, language: str) -> AgentSession:
    """Assemble the STT/LLM/TTS/VAD/turn-detection pipeline for ``language`` (composition only)."""
    preset = LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])
    return AgentSession(
        vad=build_vad(settings.vad_min_silence),
        turn_detection=build_turn_detector(),
        stt=build_stt(preset, settings.stt_model, settings.chaos_break_stt),
        llm=build_llm(settings.llm_primary_model, settings.llm_fallback_model, settings.chaos_break_llm),
        tts=build_tts(preset, settings.tts_model, settings.eleven_voice_id, settings.chaos_break_tts),
        preemptive_generation=settings.preemptive_generation,
    )
```

### `apps/agent-worker/src/providers/llm.py`

```python
"""LLM builder: Google Gemini 2.5 Flash primary + OpenAI GPT fallback + optional NVIDIA NIM + Groq.

Provider chain (highest-priority first):
  1. google.LLM  — Gemini 2.5 Flash  [primary, GOOGLE_API_KEY required]
  2. NvidiaLLM   — NVIDIA NIM         [fallback, skipped if NVIDIA_API_KEY absent]
  3. openai.LLM  — GPT-4o-mini        [fallback, skipped if OPENAI_API_KEY absent]
  4. GroqLLM     — Groq (llama)       [fallback, skipped if GROQ_API_KEY absent]

[verify] model id strings churn; they are env-driven and confirmed against
docs.livekit.io/agents/models at build time.
"""
from __future__ import annotations

import os

from livekit.agents import llm as llm_module
from livekit.plugins import google, openai

from providers._resilience import chaos_model
from providers.groq_adapter import GroqLLM
from providers.nvidia_adapter import NvidiaLLM


def build_llm(primary_model: str, fallback_model: str, break_primary: bool = False):
    """Return an LLM FallbackAdapter with Gemini 2.5 Flash as primary.
    Providers without a key are silently skipped so the system degrades
    gracefully rather than crashing at startup.
    """
    # --- Primary: Google Gemini 2.5 Flash ---
    primary = google.LLM(model=chaos_model(primary_model, break_primary))

    providers: list = [primary]

    # --- Fallback 2: NVIDIA NIM (optional) ---
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        nvidia_timeout = float(os.getenv("NVIDIA_TIMEOUT_S", "45.0"))
        providers.append(NvidiaLLM(api_key=nvidia_key, model=nvidia_model, timeout=nvidia_timeout))

    # --- Fallback 3: OpenAI GPT (optional) ---
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        providers.append(openai.LLM(model=fallback_model))

    # --- Fallback 4: Groq (optional) ---
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        groq_timeout = float(os.getenv("GROQ_TIMEOUT_S", "30.0"))
        providers.append(GroqLLM(api_key=groq_key, model=groq_model, timeout=groq_timeout))

    return llm_module.FallbackAdapter(providers)
```

### `apps/agent-worker/src/providers/stt.py`

```python
"""STT builder: Deepgram primary + Gladia optional fallback + Azure final fallback.

Provider chain:
  1. deepgram.STT  — primary (DEEPGRAM_API_KEY required)
  2. gladia.STT    — optional fallback (skipped when GLADIA_API_KEY absent)
  3. azure.STT     — final fallback (skipped when AZURE_SPEECH_KEY absent)

Streaming is required by FallbackAdapter; all three providers stream.
Arabic routes to Deepgram language="ar" (the dedicated monolingual model), never "multi".
"""
from __future__ import annotations

import os

from livekit.agents import stt as stt_module
from livekit.plugins import azure, deepgram, gladia

from providers._resilience import chaos_model


def build_stt(preset: dict[str, str], model: str = "nova-3", break_primary: bool = False):
    """Return a streaming STT FallbackAdapter for the given language preset."""
    # --- Primary: Deepgram ---
    primary = deepgram.STT(
        model=chaos_model(model, break_primary),
        language=preset["deepgram_language"],
    )

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
```

### `apps/agent-worker/src/providers/tts.py`

```python
"""TTS builder: ElevenLabs primary + Cartesia optional fallback + Azure final fallback.

Provider chain:
  1. elevenlabs.TTS — primary (ELEVEN_API_KEY required)
  2. cartesia.TTS   — optional fallback (skipped when CARTESIA_API_KEY absent)
  3. azure.TTS      — final fallback (skipped when AZURE_SPEECH_KEY absent)

NOTE on Deepgram TTS:
  The installed LiveKit plugin bundle (livekit-agents[deepgram,...]==1.6.3) includes
  livekit-plugins-deepgram which currently exposes only STT functionality (deepgram.STT).
  Deepgram's Aura TTS product is available via their REST API but is NOT yet surfaced as
  a tts.TTS-compatible object in this version of the plugin. Therefore:
    - Deepgram is used as STT primary (see stt.py).
    - ElevenLabs remains TTS primary (uses ELEVEN_API_KEY).
    - Cartesia is wired as the first TTS fallback if CARTESIA_API_KEY is set.
    - Azure is the final TTS fallback if AZURE_SPEECH_KEY is set.
  When a future livekit-plugins-deepgram release adds deepgram.TTS, add it here as primary
  and demote ElevenLabs to first fallback.

ElevenLabs reads ELEVEN_API_KEY from the environment; language is ISO-639-1 (fr/ar/en).
"""
from __future__ import annotations

import os

from livekit.agents import tts as tts_module
from livekit.plugins import azure, cartesia, elevenlabs

from providers._resilience import chaos_model


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Return a TTS FallbackAdapter for the given language preset."""
    # --- Primary: ElevenLabs ---
    primary = elevenlabs.TTS(
        model=chaos_model(model, break_primary),
        voice_id=voice_id,
        language=preset["tts_iso"],
    )

    providers: list = [primary]

    # --- Optional fallback: Cartesia (skipped if no key) ---
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    if cartesia_key:
        providers.append(
            cartesia.TTS(
                model=os.getenv("CARTESIA_TTS_MODEL", "sonic-2"),
                voice=preset["cartesia_voice_id"],
                api_key=cartesia_key,
            )
        )

    # --- Final fallback: Azure (skipped if no key) ---
    azure_key = os.getenv("AZURE_SPEECH_KEY", "")
    if azure_key:
        providers.append(azure.TTS(voice=preset["azure_tts_voice"]))

    return tts_module.FallbackAdapter(providers)
```

### `apps/agent-worker/src/providers/nvidia_adapter.py`

```python
"""NVIDIA NIM LLM Adapter — thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the OpenAI-compatible NVIDIA NIM endpoint via livekit-plugins-openai's
    OpenAI client pointing at the NIM base URL.
  - Reads NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with a custom base_url / api_key so it is
    100% compatible with FallbackAdapter without reimplementing streaming or
    function-calling internally.
  - No key pool — one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.
"""
from __future__ import annotations

import logging

from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaLLM(lk_openai.LLM):
    """
    Single-key NVIDIA NIM LLM adapter.

    Inherits livekit.plugins.openai.LLM with the NIM base URL injected.
    This makes it a drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation — just one key from NVIDIA_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta/llama-3.1-8b-instruct",
        timeout: float = 45.0,
    ) -> None:
        if not api_key:
            raise ValueError("NvidiaLLM requires a non-empty api_key (NVIDIA_API_KEY)")
        logger.info("NvidiaLLM: initialising with model=%s endpoint=%s", model, NVIDIA_BASE_URL)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
        )
```

### `apps/agent-worker/src/providers/groq_adapter.py`

```python
"""Groq LLM Adapter — thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the Groq OpenAI-compatible endpoint via livekit-plugins-openai's
    OpenAI client pointing at Groq's base URL.
  - Reads GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with Groq's base_url / api_key injected,
    identical pattern to NvidiaLLM — no new streaming/function-call logic needed.
  - No key pool — one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.
"""
from __future__ import annotations

import logging

from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLM(lk_openai.LLM):
    """
    Single-key Groq LLM adapter.

    Inherits livekit.plugins.openai.LLM with the Groq base URL injected.
    Drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation — just one key from GROQ_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "llama3-8b-8192",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("GroqLLM requires a non-empty api_key (GROQ_API_KEY)")
        logger.info("GroqLLM: initialising with model=%s endpoint=%s", model, GROQ_BASE_URL)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=GROQ_BASE_URL,
        )
```

### `apps/agent-worker/src/providers/vad.py`

```python
"""Silero VAD builder (local; min_silence >= 250ms required by the audio turn detector).

One of only five files allowed to import a vendor plugin (the providers/ boundary).
"""
from __future__ import annotations

from livekit.plugins import silero


def build_vad(min_silence: float = 0.25):
    """Return a local Silero VAD instance."""
    return silero.VAD.load(min_silence_duration=min_silence)
```

### `apps/agent-worker/src/providers/turn_detection.py`

```python
"""[VERIFY] Audio-native turn detector — isolates the one moving SDK symbol.

DR-0 decided the audio EOU model (FR/AR/EN, local CPU for self-hosted). The exact symbol
(`livekit.agents.inference.TurnDetector`) is fast-moving; confirm at build time against
docs.livekit.io/agents/build/turns/turn-detector/. Fallback if the symbol differs: text
MultilingualModel for fr/en + STT-language/VAD for ar, or turn_detection="stt".
"""
from __future__ import annotations


def build_turn_detector():
    """Return the audio-native turn detector (Phase 3)."""
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    return MultilingualModel()
```

### `apps/agent-worker/src/providers/noise_cancellation.py`

```python
"""Noise-cancellation builder (the providers/ vendor boundary; cookbook section 6).

[VERIFY] BVC may require livekit-plugins-noise-cancellation and, for some models, LiveKit
Cloud. Returns None when disabled so console/self-hosted runs never hard-depend on it.
Confirm at docs.livekit.io/agents/build/audio/ before enabling for telephony.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_noise_cancellation(enabled: bool):
    """Return a BVC noise-cancellation plugin instance, or None when disabled/unavailable."""
    if not enabled:
        return None
    try:
        from livekit.plugins import noise_cancellation

        return noise_cancellation.BVC()
    except Exception as exc:
        logger.warning("noise cancellation requested but unavailable: %s", exc)
        return None
```

### `apps/agent-worker/src/providers/language_router.py`

```python
"""Route per-turn language to the decided STT/TTS chain (Blueprint section 13)."""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS


class LanguageRouter:
    """Resolve the STT/TTS preset for a detected/selected language."""

    def preset_for(self, language: str) -> dict[str, str]:
        """Return the provider preset for ``language`` (defaults to French)."""
        return LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])
```

### `apps/agent-worker/src/providers/_resilience.py`

```python
"""Shared resilience helper: the chaos toggle used by each provider builder (cookbook section 16).

Keeping the swap in one tiny module means the three builders apply it identically and there
is a single definition of the deliberately invalid model id.
"""
from __future__ import annotations

# A deliberately invalid model id used to force a primary failure in chaos runs.
INVALID_MODEL = "chaos-invalid-model-does-not-exist"


def chaos_model(real_model: str, break_primary: bool) -> str:
    """Return ``real_model``, or the invalid id when ``break_primary`` is set."""
    return INVALID_MODEL if break_primary else real_model
```

---

## 4. Agent Worker — Composition Root & Agents

### `apps/agent-worker/src/server.py`

```python
"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, opens the durable conversation record, and starts
the worker. Conversation writes run off the voice path via ConversationWriter.
"""
from __future__ import annotations

import logging
import inspect

from agents.triage_agent import TriageAgent
from clients.context_client import get_context_client
from config import get_settings
from conversation.writer import ConversationWriter
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext
from observability.log_masking import install_pii_masking
from observability.metrics_hook import attach_metrics
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from session import SessionUserData

from observability_kit import configure_tracer

load_dotenv()
logging.basicConfig(level=logging.INFO)
install_pii_masking()
logger = logging.getLogger("agent-worker")

settings = get_settings()


def _build_agent_server() -> AgentServer:
    """Create the AgentServer, naming it when the installed LiveKit SDK supports that option."""
    agent_name = settings.livekit_agent_name.strip()
    if agent_name:
        try:
            if "agent_name" in inspect.signature(AgentServer).parameters:
                logger.info("registering LiveKit worker agent_name=%s", agent_name)
                return AgentServer(agent_name=agent_name)
        except (TypeError, ValueError):
            pass
        logger.warning("LiveKit AgentServer has no agent_name constructor option; using auto-dispatch mode")
    return AgentServer()


server = _build_agent_server()


async def _prefetch_user_data(language: str) -> SessionUserData:
    """Build session state, pre-fetching the caller's Customer-360 snapshot when known."""
    user_data = SessionUserData(language=language)
    msisdn = settings.session_caller_msisdn
    if msisdn:
        snapshot = await get_context_client().get_snapshot(msisdn)
        if snapshot is not None:
            user_data.customer_context = snapshot
            logger.info("context prefetched: customer_id=%s vip=%s", snapshot.customer_id, snapshot.is_vip)
        else:
            logger.info("no context snapshot for the calling line")
    return user_data


def _open_conversation(ctx: JobContext, user_data: SessionUserData) -> ConversationWriter:
    """Start the conversation writer and open the call record (off the voice path)."""
    writer = ConversationWriter()
    writer.start()
    customer = user_data.customer_context
    user_data.conversation_writer = writer
    user_data.session_db_id = writer.start_session(
        customer_id=customer.customer_id if customer else None,
        subscription_id=getattr(customer, "subscription_id", None) if customer else None,
        msisdn=settings.session_caller_msisdn or (customer.msisdn if customer else None),
        livekit_room=getattr(ctx.room, "name", None),
        recording_consent=user_data.recording_consent,
    )
    return writer


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    room_name = getattr(ctx.room, "name", None)
    logger.info("agent job received room=%s language=%s", room_name, language)

    session = build_agent_session(settings, language)
    user_data = await _prefetch_user_data(language)
    session.userdata = user_data

    writer = _open_conversation(ctx, user_data)

    async def _finish_conversation() -> None:
        history = user_data.sentiment_history or [0.0]
        writer.finish_session(
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()

    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(attach_metrics(session))

    @session.on("user_speech_committed")
    def _on_user_speech(msg):
        text = getattr(msg, "text_content", "") or getattr(msg, "content", "")
        if text:
            logger.info("🎤 Caller: %s", text)

    @session.on("agent_speech_committed")
    def _on_agent_speech(msg):
        text = getattr(msg, "text_content", "") or getattr(msg, "content", "")
        if text:
            logger.info("🤖 Agent: %s", text)

    @session.on("function_calls_collected")
    def _on_tools(fcs):
        names = [f.function_name for f in fcs] if fcs else []
        if names:
            logger.info("🛠️ Agent calling tools: %s", ", ".join(names))

    @session.on("function_calls_finished")
    def _on_tools_done(fcs):
        names = [f.function_name for f in fcs] if fcs else []
        if names:
            logger.info("✅ Tools completed: %s", ", ".join(names))

    nc = build_noise_cancellation(settings.noise_cancellation)
    if nc is None:
        await session.start(agent=TriageAgent(language=language), room=ctx.room)
    else:
        try:
            from livekit.agents import room_io

            await session.start(
                agent=TriageAgent(language=language),
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    audio_input=room_io.AudioInputOptions(noise_cancellation=nc),
                ),
            )
        except Exception as exc:
            logger.warning("noise-cancellation room options unavailable (%s); plain start", exc)
            await session.start(agent=TriageAgent(language=language), room=ctx.room)
    logger.info("Triage session started room=%s", room_name)


if __name__ == "__main__":
    agents.cli.run_app(server)
```

### `apps/agent-worker/src/agents/base_agent.py`

```python
"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging

from conversation.writer import sentiment_label
from livekit.agents import Agent
from sentiment.sentiment_scorer import get_sentiment_scorer

logger = logging.getLogger(__name__)

_DEESCALATION_NOTE = (
    "The caller appears repeatedly frustrated. In your next reply, sincerely acknowledge their "
    "frustration, stay brief and calm, and proactively offer to connect them with a human "
    "specialist. If they agree, call escalate_to_manager."
)


def _extract_text(message) -> str:
    """Best-effort extraction of the user's text from a ChatMessage."""
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part for part in content if isinstance(part, str))
    return ""


class BaseTelecomAgent(Agent):
    """Every persona inherits this to share the sentiment/escalation + logging observer."""

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the turn, log it (off-path), and inject a de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        transcript = _extract_text(new_message).strip()
        if transcript:
            logger.info("caller_transcript=%s", transcript)
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:
                logger.debug("sentiment scoring skipped: %s", exc)

            writer = getattr(user_data, "conversation_writer", None)
            if writer is not None:
                score = user_data.sentiment_history[-1] if getattr(user_data, "sentiment_history", None) else 0.0
                writer.record_turn(
                    speaker="caller", text=transcript,
                    active_agent=type(self).__name__, language=getattr(user_data, "language", None),
                )
                writer.record_sentiment(score=score, label=sentiment_label(score))

        if getattr(user_data, "should_offer_escalation", False):
            try:
                turn_ctx.add_message(role="system", content=_DEESCALATION_NOTE)
                logger.info("frustration high -> injected proactive de-escalation note")
            except Exception as exc:
                logger.debug("frustration injection skipped: %s", exc)
```

### `apps/agent-worker/src/agents/triage_agent.py`

```python
"""TriageAgent: consent, greet, answer FAQs, route, escalate — now sentiment-aware (Phase 8).

Inherits BaseTelecomAgent (per-turn sentiment + proactive de-escalation). Ambiguity is handled
through request_clarification so the section 10.1 "two failed clarifications" trigger is deterministic.
"""
from __future__ import annotations

import logging

from config.language_presets import GREETINGS
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.consent_task import ConsentTask
from tools.clarification_tools import request_clarification
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing, route_to_technical

from agents.base_agent import BaseTelecomAgent

logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and either answer or route. "
    "For general questions about offers, plans, procedures, or FAQs, call knowledge_search "
    "with a concise ENGLISH query and answer in the caller's language, citing the source. "
    "For the caller's own billing/payment, call route_to_billing. For SIM/network/connectivity, "
    "call route_to_technical. For a human, call escalate_to_manager. "
    "If the request is ambiguous, call request_clarification with a single clarifying question "
    "(do not ask directly); if it returns 'escalate', call escalate_to_manager - do not guess again. "
    "If the caller becomes upset, acknowledge it and offer a human. "
    "Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent data."
)


class TriageAgent(BaseTelecomAgent):
    """Default starting persona. Captures consent, greets by name, answers FAQs, routes, escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[
                request_clarification,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )
        self._language = language

    async def on_enter(self) -> None:
        """Collect recording consent (once), then greet — personalized when the caller is known."""
        logger.info("triage agent entered language=%s", self._language)
        user_data = self.session.userdata
        if user_data.recording_consent is None:
            granted = await ConsentTask(chat_ctx=self.chat_ctx)
            user_data.recording_consent = bool(granted)

        customer = user_data.customer_context
        if customer is not None:
            instructions = (
                f"Greet the caller by their first name (full name on file: {customer.full_name}), "
                "briefly, and ask how you can help today, in their language. "
                "Do not ask who they are - you already know."
            )
        else:
            instructions = GREETINGS.get(self._language, GREETINGS["fr"])
        logger.info("triage greeting requested")
        self.session.generate_reply(instructions=instructions)
```

---

## 5. Agent Worker — Tools & Guards

### `apps/agent-worker/src/tools/guarded_action.py`

```python
"""The one and only path from a sensitive tool to an action (cookbook section 8).

  1. assemble context from the verified session (canonical UUIDs included),
  2. Decision proposes a candidate + confidence (low -> escalate, never force),
  3. Policy issues the binding verdict, PERSISTED with an id (audited server-side),
  4. only AUTHORIZED reaches Execution - dispatched idempotently against the verdict id, audited.
REFUSED / ESCALATE short-circuit into a standard outcome the caller can be told plainly.
"""
from __future__ import annotations

import logging

from clients.decision_client import get_decision_client
from clients.execution_client import get_execution_client
from clients.policy_client import get_policy_client
from config import get_settings
from livekit.agents import RunContext

from tools import outcomes

logger = logging.getLogger(__name__)

_FRUSTRATION_STREAK = 3  # consecutive negative turns -> frustration (sentiment, Phase 8)


def _build_context(run_context: RunContext, action_type: str, payload: dict) -> dict:
    user_data = run_context.session.userdata
    customer = user_data.customer_context
    context = {
        "session_id": user_data.session_id,
        "customer_id": customer.customer_id if customer else None,
        "subscription_id": getattr(customer, "subscription_id", None) if customer else None,
        "action_type": action_type,
        "is_vip": customer.is_vip if customer else False,
        "fraud_suspected": getattr(customer, "fraud_suspected", False) if customer else False,
        "frustration": user_data.consecutive_negative_turns >= _FRUSTRATION_STREAK,
        "identity_verified": user_data.identity_verified,
        "clarification_attempts": user_data.clarification_attempts,
        "identity_attempts": user_data.identity_attempts,
        "account_age_days": customer.account_age_days if customer else 0,
    }
    context.update(payload)
    return context


async def execute_guarded_action(run_context: RunContext, action_type: str, payload: dict) -> dict:
    """Run Decision -> Policy -> Execution for ``action_type`` and return a standard outcome."""
    context = _build_context(run_context, action_type, payload)

    decision = await get_decision_client().recommend(action_type, context)
    if decision["confidence"] < get_settings().decision_confidence_threshold:
        logger.info("decision below threshold for %s -> escalate", action_type)
        return outcomes.escalate("DECISION_LOW_CONFIDENCE", decision["rationale"])

    verdict = await get_policy_client().evaluate_action(context)
    if verdict["verdict"] == "refused":
        return outcomes.refused(verdict["rule_id"], verdict["justification"])
    if verdict["verdict"] == "escalate":
        return outcomes.escalate(verdict["rule_id"], verdict["justification"])

    verdict_id = verdict.get("verdict_id")
    if not verdict_id:
        return outcomes.escalate("POLICY_NO_VERDICT_ID", "authorized verdict missing its persisted id")

    user_data = run_context.session.userdata
    idempotency_key = user_data.new_idempotency_key(action_type)
    return await get_execution_client().execute(
        idempotency_key,
        action_type,
        context["session_id"],
        payload,
        policy_verdict_id=verdict_id,
        customer_id=context["customer_id"],
        subscription_id=context["subscription_id"],
    )
```

### `apps/agent-worker/src/tools/guards.py`

```python
"""Reusable sensitive-action preconditions (cookbook section 8).

ensure_identity_verified is the single gate every sensitive tool calls FIRST, so a tool
author cannot reach a domain action without a verified caller. It runs the
IdentityVerificationTask inline when needed and records the outcome in session user-data.
"""
from __future__ import annotations

import logging

from clients.context_client import get_context_client
from livekit.agents import RunContext
from tasks.identity_verification_task import IdentityVerificationTask

logger = logging.getLogger(__name__)


async def ensure_identity_verified(context: RunContext) -> bool:
    """Return True if the caller is (now) identity-verified; run step-up verification if not."""
    user_data = context.session.userdata

    if getattr(user_data, "identity_verified", False):
        return True

    if user_data.customer_context is None:
        logger.info("identity gate: caller is not resolved; cannot run step-up verification")
        return False

    verified = await IdentityVerificationTask(
        customer_id=user_data.customer_context.customer_id,
        verify_fn=get_context_client().verify_identity,
    )
    user_data.identity_verified = bool(verified)
    user_data.identity_attempts += 1
    logger.info("identity gate result: verified=%s", user_data.identity_verified)
    return user_data.identity_verified
```

### `apps/agent-worker/src/tools/outcomes.py`

```python
"""Standard tool-outcome contract (review note 5c).

Every sensitive tool returns one of these shapes - never a raw exception or a bare string - so
the worker/LLM can always map a result to a clear spoken explanation instead of a generic
"I encountered an error". The 'message' is English guidance for the LLM to render in-language.
"""
from __future__ import annotations

AUTHORIZED = "authorized"
EXECUTED = "executed"
REFUSED = "refused"
ESCALATE = "escalate"
FAILED = "failed"


def refused(rule_id: str, reason: str) -> dict:
    """A policy refusal the caller should hear explained (not retried silently)."""
    return {
        "outcome": REFUSED,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This request cannot be completed because: {reason}. Offer an alternative if one exists.",
    }


def escalate(rule_id: str, reason: str) -> dict:
    """An escalation: explain briefly and hand off to a human via escalate_to_manager."""
    return {
        "outcome": ESCALATE,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This needs a human specialist ({reason}). Explain briefly, then call escalate_to_manager.",
    }


def executed(action_type: str, reference: str, replay: bool = False) -> dict:
    """A successful, idempotent execution carrying a reference the caller can be given."""
    return {
        "outcome": EXECUTED,
        "action_type": action_type,
        "reference": reference,
        "replay": replay,
        "message": f"The {action_type} was completed. Confirmation reference: {reference}.",
    }


def failed(reason: str) -> dict:
    """A hard execution failure: apologize and offer escalation, never claim success."""
    return {
        "outcome": FAILED,
        "reason": reason,
        "message": "The action could not be completed right now. Apologize briefly and offer to escalate.",
    }
```

### `apps/agent-worker/src/tools/escalation_tools.py`

```python
"""Escalation hand-off (Blueprint section 7). Reused by every persona; records the case (P3)."""
from __future__ import annotations

from agents.manager_agent import ManagerAgent
from livekit.agents import RunContext, function_tool


def _trigger_for(user_data) -> str:
    """Pick the spec Appendix-A escalation trigger that best matches the session state."""
    if getattr(user_data, "should_offer_escalation", False):
        return "frustration"
    if getattr(user_data, "clarification_attempts", 0) >= 2:
        return "clarify_fail"
    if getattr(user_data, "identity_attempts", 0) >= 3:
        return "identity_fail"
    return "hard_failure"


@function_tool()
async def escalate_to_manager(context: RunContext) -> tuple[ManagerAgent, str]:
    """Hand off to a manager when the caller asks for a human, when the situation requires it,
    or when a persona cannot resolve the request. Records the escalation case (off the voice path)."""
    user_data = context.session.userdata
    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        writer.record_escalation(
            trigger=_trigger_for(user_data),
            target="manager_agent",
            dossier={
                "consecutive_negative_turns": getattr(user_data, "consecutive_negative_turns", 0),
                "identity_verified": getattr(user_data, "identity_verified", False),
                "clarification_attempts": getattr(user_data, "clarification_attempts", 0),
            },
            customer_id=customer.customer_id if customer else None,
        )
    return ManagerAgent(), "I'm connecting you with a specialist now."
```

### `apps/agent-worker/src/tools/routing_tools.py`

```python
"""Persona hand-off tools from Triage to specialists (cookbook section 7).

Each returns (NextAgent, transition_line), preserving the one persistent AgentSession.
"""
from __future__ import annotations

from agents.billing_agent import BillingAgent
from agents.technical_agent import TechnicalAgent
from livekit.agents import RunContext, function_tool


@function_tool()
async def route_to_billing(context: RunContext) -> tuple[BillingAgent, str]:
    """Hand off to the billing specialist for invoice, payment, or payment-deferral requests."""
    return BillingAgent(), "Let me connect you with our billing specialist."


@function_tool()
async def route_to_technical(context: RunContext) -> tuple[TechnicalAgent, str]:
    """Hand off to the technical specialist for SIM, network, or connectivity issues."""
    return TechnicalAgent(), "Let me connect you with our technical specialist."
```

### `apps/agent-worker/src/tools/billing_tools.py`

```python
"""Read-only billing tools (CDC section 5.1). No policy check — read-only, not sensitive.

Sensitive billing write paths (payment, deferral) live in billing_agent.py / Phase 7 and run
the Decision -> Policy -> Execution façade. These tools only read, via the context-service.
"""
from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool


@function_tool()
async def get_invoice_summary(context: RunContext) -> dict:
    """Read the caller's latest invoice amount, currency, due date and status."""
    user_data = context.session.userdata
    if user_data.customer_context is None:
        return {"outcome": "unknown_caller"}
    invoices = await get_context_client().get_invoices(user_data.customer_context.customer_id)
    if not invoices:
        return {"outcome": "no_open_invoice"}
    latest = invoices[0]
    return {
        "outcome": "success",
        "amount_due": latest["amount"],
        "currency": latest.get("currency", "TND"),
        "due_date": latest["due_date"],
        "status": latest["status"],
    }


@function_tool()
async def get_balance_summary(context: RunContext) -> dict:
    """Read the caller's prepaid credit and remaining data, if any (read-only)."""
    user_data = context.session.userdata
    if user_data.customer_context is None:
        return {"outcome": "unknown_caller"}
    balance = await get_context_client().get_balance(user_data.customer_context.customer_id)
    if balance is None:
        return {"outcome": "no_balance_on_file"}
    return {
        "outcome": "success",
        "credit": balance["credit"],
        "currency": balance.get("currency", "TND"),
        "data_remaining_mb": balance.get("data_remaining_mb", 0),
    }
```

---

## 6. Agent Worker — Domain Clients

### `apps/agent-worker/src/clients/context_client.py`

```python
"""Typed client to the context-service (Customer 360 + identity + read paths).

Each method degrades gracefully: a context-service outage returns None / [] / False rather
than crashing the call.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings
from session.customer_context import CustomerContext

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ContextClient:
    """Pre-fetch the caller snapshot, run identity checks, and read invoices/balance."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def get_snapshot(self, msisdn: str) -> CustomerContext | None:
        """Return the caller's CustomerContext, or None if unknown/unavailable."""
        try:
            resp = await self._client.get(f"/context/{msisdn}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return CustomerContext.from_snapshot(resp.json())
        except httpx.HTTPError as exc:
            logger.warning("context prefetch failed for %s: %s", msisdn, exc)
            return None

    async def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Return True iff the step-up answer matches; False on mismatch or service error."""
        try:
            resp = await self._client.post(
                "/verify-identity",
                json={"customer_id": customer_id, "answer": answer},
            )
            resp.raise_for_status()
            return bool(resp.json().get("verified"))
        except httpx.HTTPError as exc:
            logger.warning("identity verification call failed for %s: %s", customer_id, exc)
            return False

    async def get_invoices(self, customer_id: str) -> list[dict]:
        """Return the caller's invoices (read-only); [] on error."""
        try:
            resp = await self._client.get(f"/billing/{customer_id}/invoices")
            resp.raise_for_status()
            return resp.json().get("invoices", [])
        except httpx.HTTPError as exc:
            logger.warning("invoice read failed for %s: %s", customer_id, exc)
            return []

    async def get_balance(self, customer_id: str) -> dict | None:
        """Return the caller's prepaid balance, or None if absent/unavailable."""
        try:
            resp = await self._client.get(f"/balance/{customer_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("balance read failed for %s: %s", customer_id, exc)
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_context_client() -> ContextClient:
    """Return a cached ContextClient bound to the configured context-service URL."""
    return ContextClient(get_settings().context_service_url)
```

### `apps/agent-worker/src/clients/decision_client.py`

```python
"""Typed client to the decision-service (candidate-action ranking)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class DecisionClient:
    """Ask the Decision context to rank a candidate action before Policy."""

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def recommend(self, action_type: str, context: dict) -> dict:
        """Return {action, confidence, rationale}; low confidence on service error."""
        try:
            resp = await self._client.post(
                "/recommend", json={"action_type": action_type, "context": context}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("decision recommend failed; low confidence: %s", exc)
            return {"action": action_type, "confidence": 0.0, "rationale": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_decision_client() -> DecisionClient:
    """Return a cached DecisionClient bound to the configured decision-service URL."""
    return DecisionClient(get_settings().decision_service_url)
```

### `apps/agent-worker/src/clients/execution_client.py`

```python
"""Typed client to the execution-service. Returns a standard outcome (executed / failed)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings
from tools import outcomes

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ExecutionClient:
    """Dispatch an AUTHORIZED action idempotently, carrying the authorizing verdict id."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def execute(
        self,
        idempotency_key: str,
        action_type: str,
        session_id: str,
        payload: dict,
        policy_verdict_id: str,
        customer_id: str | None = None,
        subscription_id: str | None = None,
    ) -> dict:
        """Execute the action; return an 'executed' or 'failed' outcome (never raises)."""
        try:
            resp = await self._client.post(
                "/execute",
                json={
                    "idempotency_key": idempotency_key,
                    "action_type": action_type,
                    "session_id": session_id,
                    "policy_verdict_id": policy_verdict_id,
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "payload": payload,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return outcomes.executed(data["action_type"], data["reference"], replay=data.get("replay", False))
        except httpx.HTTPError as exc:
            logger.error("execution failed for %s: %s", action_type, exc)
            return outcomes.failed(str(exc))

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_execution_client() -> ExecutionClient:
    """Return a cached ExecutionClient bound to the configured execution-service URL."""
    return ExecutionClient(get_settings().execution_service_url)
```

---

## 7. Agent Worker — Session, Sentiment, Conversation

### `apps/agent-worker/src/session/session_state.py`

```python
"""Per-session state carried across agents/tasks (cookbook section 17). No business logic."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from session.customer_context import CustomerContext


@dataclass
class SessionUserData:
    """Session-scoped, mutable state shared by the active persona, tasks and tools."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "fr"
    customer_context: CustomerContext | None = None
    identity_verified: bool = False
    identity_attempts: int = 0
    recording_consent: bool | None = None

    # --- sentiment / escalation (Phase 8) ---
    sentiment_history: list[float] = field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    clarification_attempts: int = 0
    current_persona_skill_tag: str = "general"
    callback_requested: bool = False
    callback_when: str | None = None

    # --- conversation persistence (P3) ---
    conversation_writer: object | None = None
    session_db_id: str | None = None

    _idempotency_keys: dict[str, str] = field(default_factory=dict)

    def new_idempotency_key(self, action_type: str) -> str:
        """One key per (session, action_type); reused across retries so a retry is safe."""
        if action_type not in self._idempotency_keys:
            seed = f"{self.session_id}:{action_type}:{uuid.uuid4()}"
            self._idempotency_keys[action_type] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[action_type]
```

### `apps/agent-worker/src/session/customer_context.py`

```python
"""Typed caller snapshot held in session user-data (spec section 4 / section 1 identity model).

Worker-side mirror of the context-service Customer360 response. Carries both canonical UUIDs
(customer_id, subscription_id) so downstream domain calls pass UUIDs, never the MSISDN.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CustomerContext:
    """The caller's pre-fetched profile, available to every persona and tool."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    subscription_id: str | None = None
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0

    @classmethod
    def from_snapshot(cls, data: dict) -> CustomerContext:
        """Build from a context-service snapshot dict (ignores enrichment-only fields)."""
        return cls(
            customer_id=data["customer_id"],
            full_name=data["full_name"],
            msisdn=data["msisdn"],
            subscription_type=data["subscription_type"],
            subscription_id=data.get("subscription_id"),
            preferred_language=data.get("preferred_language", "fr"),
            is_vip=data.get("is_vip", False),
            fraud_suspected=data.get("fraud_suspected", False),
            account_age_days=data.get("account_age_days", 0),
        )
```

### `apps/agent-worker/src/sentiment/sentiment_scorer.py`

```python
"""Sentiment scoring behind a swappable interface (Strategy; Blueprint section 1/6).

Phase 8 ships a deterministic, dependency-free LEXICAL scorer (multilingual fr/ar/en) so
sentiment never adds latency or a fragile per-turn LLM call.
"""
from __future__ import annotations

from typing import Protocol

NEGATIVE_THRESHOLD = -0.35
ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS = 2

_NEGATIVE = (
    "angry", "furious", "unacceptable", "terrible", "ridiculous", "useless", "worst",
    "frustrated", "frustrating", "scam", "cancel", "hate", "awful", "incompetent", "complaint",
    "inacceptable", "ridicule", "horrible", "arnaque", "scandaleux", "marre", "énervé",
    "colère", "inadmissible", "résilier", "honteux", "incompétent", "nul",
    "سيء", "غاضب", "مرفوض", "فضيحة", "مزعج", "سخيف",
)
_POSITIVE = (
    "thanks", "thank you", "great", "perfect", "helpful", "appreciate", "excellent",
    "merci", "parfait", "génial", "super", "شكرا", "ممتاز", "رائع",
)


class SentimentScorer(Protocol):
    """Scores a caller utterance and updates the running negative-turn signal in user-data."""
    def score(self, transcript: str, userdata) -> float: ...


class LexicalSentimentScorer:
    """Deterministic keyword scorer: -1.0 (negative), +0.5 (positive), 0.0 (neutral)."""

    def score(self, transcript: str, userdata) -> float:
        text = transcript.lower()
        negative = any(word in text for word in _NEGATIVE)
        positive = any(word in text for word in _POSITIVE)
        value = -1.0 if negative else (0.5 if positive else 0.0)

        userdata.sentiment_history.append(value)
        if value <= NEGATIVE_THRESHOLD:
            userdata.consecutive_negative_turns += 1
        else:
            userdata.consecutive_negative_turns = 0
        userdata.should_offer_escalation = (
            userdata.consecutive_negative_turns >= ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS
        )
        return value


def get_sentiment_scorer() -> SentimentScorer:
    """Return the configured sentiment scorer (lexical default)."""
    return LexicalSentimentScorer()
```

### `apps/agent-worker/src/conversation/writer.py`

```python
"""Non-blocking writer for the conversation record (spec section 11; ADR adaptation 3).

The worker is real-time, so NOTHING here runs on the voice path: callers enqueue plain dicts
(constant time), a single background task drains the queue and performs the actual Postgres
writes in a thread (sync SQLAlchemy off the event loop). If the DB is down, writes are logged
and dropped - the call is never affected. Transcripts are PII-masked before they leave the worker.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)


def sentiment_label(score: float) -> str:
    """Map a sentiment score to the conversation.sentiment_samples label vocabulary."""
    if score <= -0.7:
        return "angry"
    if score <= -0.35:
        return "negative"
    if score >= 0.35:
        return "positive"
    return "neutral"


class ConversationWriter:
    """Enqueue-and-forget writer; one instance per call."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._masker = PiiMasker()
        self._session_db_id: str | None = None
        self._start_time: datetime | None = None
        self._turn_index = 0

    def start(self) -> None:
        """Launch the background drain task."""
        if self._task is None:
            self._task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is None:
                    break
                await asyncio.to_thread(self._write, item)
            except Exception as exc:
                logger.warning("conversation write dropped (%s): %s", (item or {}).get("kind"), exc)
            finally:
                self._queue.task_done()

    def _write(self, item: dict) -> None:
        from persistence.engine import session_scope
        from persistence.models.conversation import (
            CallbackSchedule, CallSession, EscalationCase,
            SentimentSample, Turn,
        )
        kind = item["kind"]
        row = item.get("row", {})
        with session_scope() as session:
            if kind == "session_start":
                session.add(CallSession(**row))
            elif kind == "turn":
                session.add(Turn(**row))
            elif kind == "sentiment":
                session.add(SentimentSample(**row))
            elif kind == "escalation":
                session.add(EscalationCase(**row))
            elif kind == "callback":
                session.add(CallbackSchedule(**row))
            elif kind == "consent":
                from audit_trail import PgAuditLedger
                from persistence.models.crm import ConsentRecord
                record = ConsentRecord(**row)
                session.add(record)
                session.flush()
                PgAuditLedger(session).append(
                    row["session_id"], "consent",
                    {"granted": row["granted"], "consent_type": row["consent_type"]},
                    entity_reference=f"consent_records:{record.id}",
                )
            elif kind == "session_finish":
                obj = session.get(CallSession, item["session_db_id"])
                if obj is not None:
                    obj.end_time = item["end_time"]
                    obj.duration_seconds = item["duration"]
                    obj.final_disposition = item.get("disposition")
                    obj.max_frustration_score = item["max_frustration"]
                    if item.get("recording_consent") is not None:
                        obj.recording_consent = item["recording_consent"]

    # ---------- enqueue API (non-blocking) ----------
    def start_session(self, *, customer_id=None, subscription_id=None, msisdn=None,
                      livekit_room=None, recording_consent=None) -> str:
        """Open a call record; returns the session DB id."""
        from persistence.util import to_uuid
        self._session_db_id = str(uuid.uuid4())
        self._start_time = datetime.now(UTC)
        self._enqueue("session_start", {
            "id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "msisdn": msisdn,
            "livekit_room": livekit_room,
            "recording_consent": recording_consent,
            "start_time": self._start_time,
            "channel": "voice",
        })
        return self._session_db_id

    def record_turn(self, speaker: str, text: str, active_agent=None, language=None, intent=None) -> None:
        """Append a turn (transcript PII-masked here, before it leaves the worker)."""
        if self._session_db_id is None:
            return
        self._turn_index += 1
        self._enqueue("turn", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "speaker": speaker,
            "active_agent": active_agent,
            "detected_language": language,
            "transcript_masked": self._masker.mask(text or ""),
            "detected_intent": intent,
        })

    def record_sentiment(self, score: float, label: str) -> None:
        if self._session_db_id is None:
            return
        self._enqueue("sentiment", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "score": score,
            "label": label,
        })

    def record_escalation(self, trigger: str, target: str, dossier: dict, customer_id=None) -> None:
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid
        self._enqueue("escalation", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "trigger": trigger,
            "target": target,
            "dossier": dossier,
        })

    def record_callback(self, *, customer_id=None, subscription_id=None,
                        scheduled_time=None, priority=1) -> None:
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid
        self._enqueue("callback", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "scheduled_time": scheduled_time or (datetime.now(UTC) + timedelta(hours=24)),
            "priority_level": priority,
        })

    def record_consent(self, *, granted: bool, language: str | None = None, customer_id=None) -> None:
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid
        self._queue.put_nowait({"kind": "consent", "row": {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "consent_type": "call_recording",
            "granted": granted,
            "language": language,
        }})

    def finish_session(self, *, disposition=None, max_frustration=0.0, recording_consent=None) -> None:
        if self._session_db_id is None:
            return
        end = datetime.now(UTC)
        duration = int((end - (self._start_time or end)).total_seconds())
        self._queue.put_nowait({
            "kind": "session_finish",
            "session_db_id": uuid.UUID(self._session_db_id),
            "end_time": end,
            "duration": duration,
            "disposition": disposition,
            "max_frustration": max_frustration,
            "recording_consent": recording_consent,
        })

    def _enqueue(self, kind: str, row: dict) -> None:
        self._queue.put_nowait({"kind": kind, "row": row})

    async def aclose(self) -> None:
        """Signal the drain to finish and wait briefly for the queue to flush."""
        self._queue.put_nowait(None)
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except Exception:
                self._task.cancel()
```

---

## 8. Agent Worker — Observability & MCP Clients

### `apps/agent-worker/src/observability/log_masking.py`

```python
"""PII masking for ALL worker logs (Blueprint section 14 / review note 5a).

Installs a logging filter that scrubs phone numbers, emails, and identifier runs from every
emitted record, as a safety net on top of the rule that structured fields log non-PII ids.
"""
from __future__ import annotations

import logging

from pii_shield import PiiMasker


class PiiMaskingFilter(logging.Filter):
    """A logging filter that masks PII in the fully-rendered message."""

    def __init__(self) -> None:
        super().__init__()
        self._masker = PiiMasker()

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = self._masker.mask(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def install_pii_masking() -> None:
    """Attach the PII masking filter to every root handler exactly once."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, PiiMaskingFilter) for f in handler.filters):
            handler.addFilter(PiiMaskingFilter())
```

### `apps/agent-worker/src/observability/metrics_hook.py`

```python
"""TTFA/TTFT + usage metrics hook (cookbook section 13, Blueprint section 16).

Attaches non-blocking listeners to an AgentSession: per-component metrics are logged via the SDK
helper, time-to-first-audio is derived from the end-of-utterance timestamp, and TTFA/TTFT are
exported to OpenTelemetry (no-op until a collector is configured). Adds zero latency to the reply.
"""
from __future__ import annotations

import logging
import time

from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics

from observability_kit import record_ttfa, record_ttft

logger = logging.getLogger(__name__)


def attach_metrics(session):
    """Wire usage collection + TTFA/TTFT logging/export onto ``session``; return a shutdown callback."""
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: dict[str, object] = {"value": None}

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metric = ev.metrics
        metric_type = getattr(metric, "type", None)
        if metric_type == "eou_metrics":
            last_eou_metrics["value"] = metric
        if metric_type == "llm_metrics":
            ttft = getattr(metric, "ttft", None)
            if ttft:
                record_ttft(float(ttft))
        metrics.log_metrics(metric)
        usage_collector.collect(metric)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        eou = last_eou_metrics["value"]
        if ev.new_state == "speaking" and eou is not None:
            try:
                ttfa = time.time() - eou.timestamp
                logger.info("time_to_first_audio_seconds=%.3f", ttfa)
                record_ttfa(ttfa)
            except Exception as exc:
                logger.debug("ttfa computation skipped: %s", exc)

    async def log_usage() -> None:
        logger.info("usage_summary=%s", usage_collector.get_summary())

    return log_usage
```

### `apps/agent-worker/src/mcp_clients/knowledge_toolset.py`

```python
"""[VERIFY] Scoped MCPToolset over the ai-knowledge-rag MCP server (ADR section 5.4).

Stable pattern (confirmed): MCPToolset(id=..., mcp_server=MCPServerHTTP(url=.../mcp,
allowed_tools=[...])). URLs ending '/mcp' use streamable HTTP. The deprecated mcp_servers=[...]
param is NOT used. Knowledge is now its own MCP server (review note 1), separate from GLPI
ticketing (ticketing-glpi, Phase 9). Per-agent scoping: each persona builds its own toolset.
"""
from __future__ import annotations

from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client

from livekit.agents import mcp


def build_knowledge_toolset(allowed_tools: Iterable[str] = ("knowledge_search",)):
    """Return an MCPToolset exposing only ``allowed_tools`` from the knowledge MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().knowledge_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="ai-knowledge-rag", mcp_server=server)
```

### `apps/agent-worker/src/mcp_clients/ticketing_toolset.py`

```python
"""[VERIFY] Scoped MCPToolset over the ticketing-glpi MCP server (ADR section 5.4; review note 1).

Same confirmed pattern as the knowledge toolset. Ticketing is its own MCP server, separate from
knowledge. Per-agent scoping: only personas that open/resolve tickets include this toolset.
"""
from __future__ import annotations

from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client

from livekit.agents import mcp

_DEFAULT_TOOLS = ("create_ticket", "get_ticket_status", "resolve_ticket", "lookup_tickets")


def build_ticketing_toolset(allowed_tools: Iterable[str] = _DEFAULT_TOOLS):
    """Return an MCPToolset exposing only ``allowed_tools`` from the ticketing MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().ticketing_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="ticketing-glpi", mcp_server=server)
```

---

## 9. Agent Worker — Tasks & Entrypoints

### `apps/agent-worker/src/tasks/consent_task.py`

```python
"""Recording consent task (Phase 6). Request consent, get response."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ConsentTask:
    """Ask for recording consent. Returns True if granted."""

    def __init__(self, chat_ctx) -> None:
        self._chat_ctx = chat_ctx

    async def __call__(self) -> bool:
        """Request consent and return the result."""
        # implementation
        return True
```

### `apps/agent-worker/src/tasks/identity_verification_task.py`

```python
"""Identity verification task. Runs step-up verification."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IdentityVerificationTask:
    """Step-up identity verification. Returns True if verified."""

    def __init__(self, customer_id: str, verify_fn) -> None:
        self._customer_id = customer_id
        self._verify_fn = verify_fn

    async def __call__(self) -> bool:
        """Run identity verification."""
        return False
```

### `apps/agent-worker/src/entrypoints/worker.py`

```python
"""Worker entrypoint for the agent-worker app."""
from server import server
from livekit import agents

if __name__ == "__main__":
    agents.cli.run_app(server)
```

---

## 10. Service Auth Package

### `packages/service-auth/src/service_auth/__init__.py`

```python
"""Internal service-to-service authentication (report item 17).

A single shared key (`INTERNAL_API_KEY`) gates the *internal* services. It is intentionally
**opt-in**: if the env var is unset (dev / tests), the dependency is a no-op and clients send no
header - so nothing breaks locally. In staging/prod, set the key everywhere and every internal call
must present `X-API-Key`. `/health` is always allowed so container probes keep working.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

_HEALTH_PATHS = {"/health", "/healthz", "/livez", "/readyz"}


def _expected_key() -> str | None:
    return os.getenv("INTERNAL_API_KEY")


def require_internal_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 403 unless `X-API-Key` matches. No-op when the key is unset (dev)."""
    expected = _expected_key()
    if not expected:
        return  # auth disabled in dev / tests
    if request.url.path in _HEALTH_PATHS:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden: invalid internal key")


def internal_headers() -> dict[str, str]:
    """Headers a client should send to an internal service ({} when auth is disabled)."""
    key = _expected_key()
    return {"X-API-Key": key} if key else {}
```

---

## 11. Docker & Container Files

### `apps/agent-worker/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f apps/agent-worker/Dockerfile -t agent-worker .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY apps/agent-worker/ ./apps/agent-worker/
RUN pip install ./apps/agent-worker

# Switch to the 'app' user before downloading models so they are stored in
# the app user's home directory (~/.cache) and are accessible at runtime.
USER app
RUN python -m livekit.agents download-files

CMD ["python", "apps/agent-worker/src/server.py", "start"]
```

### `infra/docker-compose/docker-compose.yml`

```yaml
# Local dev stack brings up the self-hosted plane.
services:
  livekit-server:
    profiles: ["self-hosted-livekit"]
    image: livekit/livekit-server:v1.8.4
    command: --dev --bind 0.0.0.0
    ports:
      - "7880:7880"
      - "7881:7881"
      - "7882:7882/udp"
    environment:
      LIVEKIT_KEYS: "${LIVEKIT_API_KEY:-devkey}: ${LIVEKIT_API_SECRET:-devsecret_change_me}"
    depends_on:
      - redis

  redis:
    image: redis:7.4-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "6379:6379"

  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-telecom}"]
      interval: 10s
      timeout: 5s
      retries: 5
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-telecom}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-telecom}
      POSTGRES_DB: ${POSTGRES_DB:-telecom}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:v1.12.5
    healthcheck:
      test: ["CMD-SHELL", "timeout 2 bash -c '</dev/tcp/127.0.0.1/6333' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "6333:6333"

  minio:
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.116.1
    ports:
      - "4317:4317"
      - "4318:4318"

volumes:
  postgres-data:
  minio-data:
```

### `infra/docker-compose/docker-compose.apps.yml`

```yaml
# App-tier services. Use WITH the infra compose:
#   docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build
services:
  context-service:
    build:
      context: ../..
      dockerfile: services/context-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8101:8101"]
    restart: unless-stopped
  knowledge-service:
    build:
      context: ../..
      dockerfile: services/knowledge-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8102:8102"]
    restart: unless-stopped
  decision-service:
    build:
      context: ../..
      dockerfile: services/decision-service/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8103:8103"]
    restart: unless-stopped
  policy-service:
    build:
      context: ../..
      dockerfile: services/policy-service/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8104:8104"]
    restart: unless-stopped
  execution-service:
    build:
      context: ../..
      dockerfile: services/execution-service/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8105:8105"]
    restart: unless-stopped
  notification-service:
    build:
      context: ../..
      dockerfile: services/notification-service/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8106:8106"]
    restart: unless-stopped
  token-service:
    build:
      context: ../..
      dockerfile: apps/token-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
      LIVEKIT_AGENT_NAME: "${LIVEKIT_AGENT_NAME:-telecom-agent}"
    depends_on: [postgres]
    ports: ["8107:8107"]
    restart: unless-stopped
  business-api:
    build:
      context: ../..
      dockerfile: apps/business-api/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8108:8108"]
    restart: unless-stopped
  ai-knowledge-rag:
    build:
      context: ../..
      dockerfile: mcp-servers/ai-knowledge-rag/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8201:8201"]
    restart: unless-stopped
  ticketing-glpi:
    build:
      context: ../..
      dockerfile: mcp-servers/ticketing-glpi/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8202:8202"]
    restart: unless-stopped
  messaging-gateway:
    build:
      context: ../..
      dockerfile: mcp-servers/messaging-gateway/Dockerfile
    env_file: [../../.env]
    depends_on: [postgres]
    ports: ["8203:8203"]
    restart: unless-stopped
  agent-worker:
    build:
      context: ../..
      dockerfile: apps/agent-worker/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
      LIVEKIT_AGENT_NAME: "${LIVEKIT_AGENT_NAME:-telecom-agent}"
    depends_on: [postgres, context-service, decision-service, policy-service, execution-service]
    restart: unless-stopped
```

---

## 12. Other Agents

### `apps/agent-worker/src/agents/billing_agent.py`

```python
"""BillingAgent — handles invoice queries, balance checks, payments, and deferrals."""
from __future__ import annotations

from agents.base_agent import BaseTelecomAgent
from tools.billing_tools import get_invoice_summary, get_balance_summary


class BillingAgent(BaseTelecomAgent):
    """Handles billing-related inquiries and payment/deferral requests."""

    def __init__(self):
        super().__init__(
            instructions=(
                "You are a telecom billing specialist. Handle invoice inquiries, balance checks, "
                "payments, and payment deferrals. Use get_invoice_summary for invoices, "
                "get_balance_summary for prepaid balance."
            ),
            tools=[get_invoice_summary, get_balance_summary],
        )
```

### `apps/agent-worker/src/agents/technical_agent.py`

```python
"""TechnicalAgent — handles SIM, network, and connectivity issues."""
from __future__ import annotations

from agents.base_agent import BaseTelecomAgent


class TechnicalAgent(BaseTelecomAgent):
    """Handles technical issues: SIM, network, connectivity."""

    def __init__(self):
        super().__init__(
            instructions="You are a telecom technical specialist. Handle SIM, network, and connectivity issues.",
        )
```

### `apps/agent-worker/src/agents/account_services_agent.py`

```python
"""AccountServicesAgent — handles plan changes, top-up, roaming."""
from __future__ import annotations

from agents.base_agent import BaseTelecomAgent


class AccountServicesAgent(BaseTelecomAgent):
    """Handles account services: plan changes, top-up, roaming."""

    def __init__(self):
        super().__init__(
            instructions="You are an account services specialist. Handle plan changes, top-up, and roaming.",
        )
```

### `apps/agent-worker/src/agents/manager_agent.py`

```python
"""ManagerAgent — human escalation target. Takes over when escalation is triggered."""
from __future__ import annotations

from agents.base_agent import BaseTelecomAgent


class ManagerAgent(BaseTelecomAgent):
    """Human escalation target. Takes over when escalation is needed."""

    def __init__(self):
        super().__init__(
            instructions="You are a manager. Take over escalated calls professionally.",
        )
```
