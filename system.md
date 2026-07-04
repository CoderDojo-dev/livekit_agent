# Telecom AI Voice Agent Platform — System Documentation

**Platform**: Real-time multilingual voice AI agent for telecom customer support
**Stack**: Python 3.12, LiveKit Agents, FastAPI, PostgreSQL, Redis, Qdrant, Docker
**Languages**: French (primary), Arabic, English
**LiveKit**: Cloud (`wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud`)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Directory Structure](#2-directory-structure)
3. [Configuration System](#3-configuration-system)
4. [Agent Worker — Core Logic](#4-agent-worker--core-logic)
5. [Providers — STT / LLM / TTS / VAD](#5-providers--stt-llm-tts-vad)
6. [Agents — Triage, Billing, Technical, Account, Manager](#6-agents--triage-billing-technical-account-manager)
7. [Tools & Guards](#7-tools--guards)
8. [Domain Services](#8-domain-services)
9. [MCP Servers](#9-mcp-servers)
10. [Infrastructure](#10-infrastructure)
11. [Docker Deployment](#11-docker-deployment)
12. [CI/CD](#12-cicd)
13. [Key Files Reference](#13-key-files-reference)

---

## 1. Architecture Overview

### 1.1 Call Flow

```
Caller (browser/app)
    │
    ▼
LiveKit Cloud
    │  ← WebRTC audio stream
    ▼
┌─────────────────────────────┐
│  agent-worker (LiveKit Agent) │  ← Voice pipeline (STT/LLM/TTS/VAD)
│  apps/agent-worker/           │
└─────────────────────────────┘
    │ /grpc/http
    ├──► domain services (context, decision, policy, execution, notification)
    ├──► MCP tools (ticketing, knowledge, messaging)
    └──► LLM providers (Gemini, NVIDIA, OpenAI, Groq)

token-service   ← mints LiveKit JWT for browser callers
```

### 1.2 Provider Chain (per call)

```
STT:  Deepgram nova-3 → Gladia → Azure STT
TTS:  ElevenLabs Flash v2.5 → Cartesia sonic-2 → Azure TTS
LLM:  Gemini 2.5 Flash → NVIDIA NIM → OpenAI GPT-4o-mini → Groq
VAD:  Silero VAD (local CPU)
```

### 1.3 Technology Stack

| Component | Technology |
|---|---|
| Voice transport | LiveKit Cloud (WebRTC) |
| Voice AI framework | `livekit-agents==1.6.3` |
| STT | Deepgram nova-3 (primary), Gladia, Azure |
| TTS | ElevenLabs Flash v2.5 (primary), Cartesia, Azure |
| LLM | Gemini 2.5 Flash (primary), NVIDIA NIM, OpenAI GPT-4o-mini, Groq |
| VAD | Silero (local) |
| Turn detection | LiveKit multilingual model |
| API framework | FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy |
| Cache | Redis 7.4 |
| Vector search | Qdrant v1.12.5 |
| Object storage | MinIO |
| Observability | OpenTelemetry → OTEL collector |
| MCP | `mcp>=1.12,<2` (Python MCP SDK) |
| Process management | Honcho (dev), Docker (prod) |

---

## 2. Directory Structure

```
telecom-ai-agent-platform/
├── .env                              # 234-line env config (all API keys, URLs, settings)
├── .env.example
├── Makefile                          # make install/dev/up/down/health/rebuild/test
├── Procfile                          # 16-process honcho definition
├── pyproject.toml                    # Ruff/mypy root config
│
├── apps/
│   ├── agent-worker/
│   │   ├── Dockerfile               # python:3.12-slim, installs all packages + apps
│   │   ├── pyproject.toml           # livekit-agents[all-plugins]==1.6.3, mcp>=1.12
│   │   └── src/
│   │       ├── server.py            # COMPOSITION ROOT — AgentServer entrypoint
│   │       ├── config/
│   │       │   ├── settings.py      # 25+ env vars via pydantic_settings
│   │       │   └── language_presets.py  # Per-language keys for STT/TTS providers
│   │       ├── providers/           # VENDOR BOUNDARY — only place livekit.plugins imports
│   │       │   ├── llm.py           # build_llm() — FallbackAdapter chain
│   │       │   ├── stt.py           # build_stt() — Deepgram primary
│   │       │   ├── tts.py           # build_tts() — ElevenLabs primary
│   │       │   ├── nvidia_adapter.py # NvidiaLLM (inherits openai.LLM, NIM base URL)
│   │       │   ├── groq_adapter.py   # GroqLLM (inherits openai.LLM, Groq base URL)
│   │       │   ├── vad.py           # Silero VAD builder
│   │       │   ├── turn_detection.py # LiveKit MultilingualModel
│   │       │   ├── noise_cancellation.py
│   │       │   ├── session_factory.py # assembles AgentSession with all providers
│   │       │   ├── language_router.py
│   │       │   └── _resilience.py    # chaos toggle — invalid model ID for testing
│   │       ├── agents/
│   │       │   ├── triage_agent.py   # Primary voice agent (greets, routes, escalates)
│   │       │   ├── billing_agent.py  # Invoice/balance/payment/deferral
│   │       │   ├── technical_agent.py # SIM/network/connectivity
│   │       │   ├── account_services_agent.py # plan/top-up/roaming
│   │       │   ├── manager_agent.py  # Human escalation target
│   │       │   └── base_agent.py     # Sentiment tracking, escalation logic
│   │       ├── tools/
│   │       │   ├── guarded_action.py # D→P→E facade — all sensitive ops go through here
│   │       │   ├── guards.py         # Identity verification gate
│   │       │   ├── escalation_tools.py
│   │       │   ├── billing_tools.py
│   │       │   ├── technical_tools.py
│   │       │   ├── routing_tools.py
│   │       │   ├── clarification_tools.py
│   │       │   ├── account_tools.py
│   │       │   └── outcomes.py       # Standardized outcome contract
│   │       ├── tasks/               # Task groups (consent, identity, payment, callback)
│   │       ├── session/             # SessionUserData, SessionState, CustomerContext
│   │       ├── conversation/writer.py # Durable conversation record (off voice path)
│   │       ├── telephony/sip_transfer.py
│   │       ├── sentiment/sentiment_scorer.py # Lexical sentiment scoring
│   │       ├── observability/       # PII masking, TTFA/TTFT metrics hooks
│   │       ├── clients/             # HTTP clients to domain services
│   │       │   ├── context_client.py
│   │       │   ├── decision_client.py
│   │       │   ├── policy_client.py
│   │       │   ├── execution_client.py
│   │       │   ├── notification_client.py
│   │       │   └── routing_client.py
│   │       └── mcp_clients/
│   │           ├── knowledge_toolset.py  # MCP tool wrapper for knowledge search
│   │           └── ticketing_toolset.py  # MCP tool wrapper for GLPI ticketing
│   │
│   ├── token-service/
│   │   └── src/token_service/main.py  # FastAPI — mints LiveKit JWT tokens
│   │
│   ├── business-api/
│   │   └── src/business_api/
│   │       ├── main.py             # FastAPI — customer_360, session_detail, KPIs
│   │       ├── repositories.py     # SQLAlchemy reads
│   │       └── jobs/               # retention, integrity background jobs
│   │
│   ├── client-widget/              # React/Vite — browser caller UI
│   └── supervisor-dashboard/       # React/Vite — back-office dashboard
│
├── services/
│   ├── context-service/   :8101   # Customer-360 (CRM reads, invoices, balance)
│   ├── knowledge-service/ :8102   # RAG search (lexical + Qdrant vector)
│   ├── decision-service/  :8103   # Action ranking with confidence scores
│   ├── policy-service/    :8104   # Deterministic rules engine (AUTHORIZED/REFUSED/ESCALATE)
│   ├── execution-service/ :8105   # Idempotent action dispatch (mock vs live)
│   └── notification-service/:8106 # SMS/WhatsApp/Email channels
│
├── packages/
│   ├── domain-core/       # Value objects, entities, port interfaces
│   ├── persistence/       # SQLAlchemy models, engine, Alembic migrations, seeds
│   ├── audit-trail/       # Hash-chained append-only ledger
│   ├── pii-shield/        # PII masking (phone, email, ID patterns)
│   ├── observability-kit/ # OTel tracer configuration
│   ├── service-auth/      # Internal API key authentication (X-API-Key)
│   ├── cache/             # Redis / NullCache client
│   ├── object-storage/    # MinIO / NullStore
│   ├── notification-client/
│   └── integration-adapters/ # Factory for legacy system adapters (billing, OCS, CRM, GLPI, NMS)
│
├── mcp-servers/
│   ├── ai-knowledge-rag/  :8201   # MCP tool: knowledge search (Qdrant)
│   ├── ticketing-glpi/    :8202   # MCP tool: GLPI ticket CRUD
│   └── messaging-gateway/  :8203   # MCP tool: messaging/notification ops
│
├── infra/
│   ├── docker-compose/
│   │   ├── docker-compose.yml     # Infrastructure: postgres:16, redis:7.4, qdrant, minio, otel
│   │   └── docker-compose.apps.yml # App services (12 services)
│   └── helm/telecom-platform/      # Full K8s Helm chart (infra + services + gateway + otel)
│
├── deploy/
│   ├── postgres/          # Standalone postgres
│   ├── otel/             # OTEL collector + Prometheus
│   ├── gateway/          # Nginx API gateway
│   ├── secrets/          # Docker secrets + .env.example
│   ├── backup/           # pg_dump scripts
│   └── helm/telecom-agent/  # Agent deployment Helm chart
│
├── docs/                 # Architecture docs, phase READMEs, ADRs, patches
├── scripts/              # PowerShell dev scripts, health_check.py, run_tests.py
└── tests/load/           # Load test scripts
```

---

## 3. Configuration System

### 3.1 Environment File — `.env`

All configuration flows through the root `.env` file. Key sections:

**LiveKit Transport** (used by agent-worker + token-service):
```env
LIVEKIT_URL=wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud
LIVEKIT_API_KEY=API4oF2JZPKv5s7
LIVEKIT_API_SECRET=K2vSLuHfjm5Psu95A7yuXUVnqGMR2qlWl1O6p0niSYE
LIVEKIT_AGENT_NAME=telecom-agent
```

**API Keys** (STT/TTS/LLM providers):
```env
DEEPGRAM_API_KEY=REDACTED_DEEPGRAM_API_KEY  # STT primary ✓
ELEVEN_API_KEY=                                             # TTS primary — EMPTY
GOOGLE_API_KEY=REDACTED_GOOGLE_API_KEY           # LLM primary ✓
OPENAI_API_KEY=sk-proj-...                                 # LLM fallback — quota exceeded ⚠
NVIDIA_API_KEY=nvapi-xq04a5nm6KdPoQ6pjuIMlGn...          # LLM fallback — configured
GROQ_API_KEY=gsk_BTE4b9zhpYE5VmU3wm5MWGdyb...             # LLM fallback — decommissioned model ⚠
GLADIA_API_KEY=a7a21c8a-27b7-4095-81db-...               # STT optional fallback
CARTESIA_API_KEY=sk_car_tofNa8mAPgQWd7uVqEiQom          # TTS optional fallback
AZURE_SPEECH_KEY=                                          # STT/TTS final fallback — EMPTY
```

**Model Selection**:
```env
STT_MODEL=nova-3
TTS_MODEL=eleven_flash_v2_5
ELEVEN_VOICE_ID=EXAVITQu4vr4xnSDxMaL
LLM_PRIMARY_MODEL=gemini-2.5-flash-latest          # ⚠ Should be gemini-3.5-flash
LLM_FALLBACK_MODEL=gpt-4o-mini
NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b
GROQ_MODEL=llama3-8b-8192                          # ⚠ Decommissioned by Groq
```

**Domain Service URLs** (container networking):
```env
CONTEXT_SERVICE_URL=http://localhost:8101
DECISION_SERVICE_URL=http://localhost:8103
POLICY_SERVICE_URL=http://localhost:8104
EXECUTION_SERVICE_URL=http://localhost:8105
NOTIFICATION_SERVICE_URL=http://localhost:8106
KNOWLEDGE_MCP_URL=http://localhost:8201/mcp
TICKETING_MCP_URL=http://localhost:8202/mcp
MESSAGING_MCP_URL=http://localhost:8203/mcp
```

**Observability**:
```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317   # OTEL collector — must be running
```

### 3.2 Settings — `apps/agent-worker/src/config/settings.py`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LiveKit
    livekit_url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("devsecret_change_me", alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("telecom-agent", alias="LIVEKIT_AGENT_NAME")

    # Language
    supported_languages: str = Field("fr,ar,en")
    default_language: str = Field("fr")
    session_language: str = Field("fr")
    session_caller_msisdn: str = Field("")

    # STT
    stt_model: str = Field("nova-3", alias="STT_MODEL")

    # TTS
    tts_model: str = Field("eleven_flash_v2_5")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL")

    # LLM
    llm_primary_model: str = Field("gemini-2.5-flash-latest", alias="LLM_PRIMARY_MODEL")  # ⚠ wrong
    llm_fallback_model: str = Field("gpt-4o-mini")

    # NVIDIA NIM
    nvidia_api_key: str = Field("")
    nvidia_model: str = Field("meta/llama-3.1-8b-instruct")
    nvidia_timeout_s: float = 45.0

    # Groq
    groq_api_key: str = Field("")
    groq_model: str = Field("llama3-8b-8192")  # ⚠ decommissioned
    groq_timeout_s: float = 30.0

    # VAD
    vad_min_silence: float = 0.25
    preemptive_generation: bool = True
    noise_cancellation: bool = False

    # Chaos toggles
    chaos_break_stt: bool = False
    chaos_break_llm: bool = False
    chaos_break_tts: bool = False

    # Domain services
    context_service_url: str = Field("http://localhost:8101")
    decision_service_url: str = Field("http://localhost:8103")
    policy_service_url: str = Field("http://localhost:8104")
    execution_service_url: str = Field("http://localhost:8105")
    notification_service_url: str = Field("http://localhost:8106")
    knowledge_mcp_url: str = Field("http://localhost:8201/mcp")
    ticketing_mcp_url: str = Field("http://localhost:8202/mcp")
```

---

## 4. Agent Worker — Core Logic

### 4.1 Entry Point — `server.py`

`apps/agent-worker/src/server.py` is the **composition root**. It:
1. Loads `.env` via `dotenv.load_dotenv()`
2. Installs PII masking
3. Configures the OTel tracer
4. Creates `AgentServer` (LiveKit's worker server)
5. Starts a voice session via `@server.rtc_session()` decorator

The entrypoint function `entrypoint(ctx: JobContext)` assembles a full `AgentSession` per call:

```python
@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    language = settings.session_language  # from .env
    session = build_agent_session(settings, language)  # assembles STT/LLM/TTS/VAD
    user_data = await _prefetch_user_data(language)   # fetches Customer-360
    writer = _open_conversation(ctx, user_data)        # opens durable record

    # Attaches event listeners for speech/tool logging
    @session.on("user_speech_committed")
    def _on_user_speech(msg): ...

    @session.on("agent_speech_committed")
    def _on_agent_speech(msg): ...

    @session.on("function_calls_collected")
    def _on_tools(fcs): ...

    @session.on("function_calls_finished")
    def _on_tools_done(fcs): ...

    # Starts the voice session with TriageAgent
    await session.start(agent=TriageAgent(language=language), room=ctx.room)
```

### 4.2 Session Factory — `providers/session_factory.py`

Assembles all providers into one `AgentSession`:

```python
def build_agent_session(settings: Settings, language: str) -> AgentSession:
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

### 4.3 Language Presets — `config/language_presets.py`

Each language provides all keys consumed by the STT/TTS builders:

```python
LANGUAGE_PRESETS = {
    "fr": {
        "deepgram_language": "fr",           # deepgram.STT(language=...)
        "azure_stt_locale": "fr-FR",          # azure.STT(language=...)
        "gladia_language": "fr",              # gladia.STT(languages=[...])
        "tts_iso": "fr",                       # elevenlabs.TTS(language=...)
        "azure_tts_voice": "fr-FR-DeniseNeural", # azure.TTS(voice=...)
        "cartesia_voice_id": "a249eaff-...",   # cartesia.TTS(voice=...)
    },
    "ar": {
        "deepgram_language": "ar",             # single-language model — never "multi"
        "azure_stt_locale": "ar-EG",
        "gladia_language": "ar",
        "tts_iso": "ar",
        "azure_tts_voice": "ar-EG-SalmaNeural",
        "cartesia_voice_id": "79743797-...",
    },
    "en": {
        "deepgram_language": "en",
        "azure_stt_locale": "en-US",
        "gladia_language": "en",
        "tts_iso": "en",
        "azure_tts_voice": "en-US-JennyNeural",
        "cartesia_voice_id": "694f9389-...",
    },
}
```

---

## 5. Providers — STT / LLM / TTS / VAD

### 5.1 STT Builder — `providers/stt.py`

**Chain**: Deepgram → Gladia → Azure

```python
def build_stt(preset: dict, model: str = "nova-3", break_primary: bool = False):
    primary = deepgram.STT(
        model=chaos_model(model, break_primary),
        language=preset["deepgram_language"],  # "fr", "ar", or "en"
    )
    providers = [primary]

    # Optional: Gladia
    if gladia_key := os.getenv("GLADIA_API_KEY", ""):
        providers.append(gladia.STT(languages=[preset["gladia_language"]], api_key=gladia_key))

    # Optional: Azure
    if azure_key := os.getenv("AZURE_SPEECH_KEY", ""):
        providers.append(azure.STT(language=preset["azure_stt_locale"]))

    return stt_module.FallbackAdapter(providers)
```

**Live evidence from logs**: `model_name=nova-3, model_provider=Deepgram` — Deepgram STT is working.

### 5.2 TTS Builder — `providers/tts.py`

**Chain**: ElevenLabs → Cartesia → Azure

```python
def build_tts(preset: dict, model: str, voice_id: str, break_primary: bool = False):
    primary = elevenlabs.TTS(
        model=chaos_model(model, break_primary),  # "eleven_flash_v2_5"
        voice_id=voice_id,                          # "EXAVITQu4vr4xnSDxMaL"
        language=preset["tts_iso"],                  # "fr", "ar", "en"
    )
    providers = [primary]

    # Optional: Cartesia
    if cartesia_key := os.getenv("CARTESIA_API_KEY", ""):
        providers.append(cartesia.TTS(
            model=os.getenv("CARTESIA_TTS_MODEL", "sonic-2"),
            voice=preset["cartesia_voice_id"],
            api_key=cartesia_key,
        ))

    # Optional: Azure
    if azure_key := os.getenv("AZURE_SPEECH_KEY", ""):
        providers.append(azure.TTS(voice=preset["azure_tts_voice"]))

    return tts_module.FallbackAdapter(providers)
```

**Note**: Deepgram TTS is NOT available in `livekit-plugins-deepgram==1.6.3`. The plugin only exposes `deepgram.STT`. ElevenLabs is the TTS primary. When `livekit-plugins-deepgram` adds `deepgram.TTS`, ElevenLabs should be demoted to fallback.

### 5.3 LLM Builder — `providers/llm.py`

**Chain**: Gemini → NVIDIA NIM → OpenAI GPT → Groq

```python
def build_llm(primary_model: str, fallback_model: str, break_primary: bool = False):
    # Primary: Google Gemini
    primary = google.LLM(model=chaos_model(primary_model, break_primary))

    providers = [primary]

    # Fallback: NVIDIA NIM (optional — only if NVIDIA_API_KEY set)
    if nvidia_key := os.getenv("NVIDIA_API_KEY", ""):
        nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        providers.append(NvidiaLLM(api_key=nvidia_key, model=nvidia_model, timeout=45.0))

    # Fallback: OpenAI GPT (optional — only if OPENAI_API_KEY set)
    if openai_key := os.getenv("OPENAI_API_KEY", ""):
        providers.append(openai.LLM(model=fallback_model))

    # Fallback: Groq (optional — only if GROQ_API_KEY set)
    if groq_key := os.getenv("GROQ_API_KEY", ""):
        groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        providers.append(GroqLLM(api_key=groq_key, model=groq_model, timeout=30.0))

    return llm_module.FallbackAdapter(providers)
```

**Order**: `[gemini, nvidia, openai, groq]`

### 5.4 NVIDIA Adapter — `providers/nvidia_adapter.py`

Inherits `livekit.plugins.openai.LLM` with NIM base URL injected. Single-key, no pool.

```python
class NvidiaLLM(lk_openai.LLM):
    def __init__(self, *, api_key: str, model: str = "meta/llama-3.1-8b-instruct", timeout: float = 45.0):
        super().__init__(
            model=model,
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
```

The NIM endpoint is `https://integrate.api.nvidia.com/v1`. Model configured via `.env`: `NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b`.

### 5.5 Groq Adapter — `providers/groq_adapter.py`

Same pattern as NVIDIA — inherits `openai.LLM` with Groq base URL.

```python
class GroqLLM(lk_openai.LLM):
    def __init__(self, *, api_key: str, model: str = "llama3-8b-8192", timeout: float = 30.0):
        super().__init__(
            model=model,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
```

**CRITICAL**: `GROQ_MODEL=llama3-8b-8192` is decommissioned. Must change to `llama-3.1-8b-instant`.

### 5.6 VAD — `providers/vad.py`

```python
def build_vad(min_silence: float = 0.25):
    from livekit.plugins import silero
    return silero.VAD(min_silence=min_silence)
```

Silero VAD runs locally on CPU. No API key required.

### 5.7 Turn Detection — `providers/turn_detection.py`

```python
def build_turn_detector():
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    return MultilingualModel()
```

Uses `lk_end_of_utterance_multilingual` model. **This requires a LiveKit inference executor** — without it, the error `no inference executor` appears. This is a LiveKit Cloud limitation.

### 5.8 Resilience / Chaos Toggle — `providers/_resilience.py`

```python
INVALID_MODEL = "chaos-invalid-model-does-not-exist"

def chaos_model(real_model: str, break_primary: bool) -> str:
    return INVALID_MODEL if break_primary else real_model
```

Used by all three builders when `CHAOS_BREAK_*=true` in `.env`.

---

## 6. Agents — Triage, Billing, Technical, Account, Manager

All five agents inherit from `base_agent.py`. They are LiveKit `Agent` subclasses.

### 6.1 TriageAgent — `agents/triage_agent.py`

Primary voice agent. Entry point for all calls. Responsibilities:
1. Greet the caller (in correct language using `GREETINGS` from `language_presets.py`)
2. Check recording consent
3. Route to appropriate specialist agent based on caller intent
4. Handle escalation when policy requires it

```python
class TriageAgent(Agent):
    def __init__(self, language: str):
        super().__init__(
            instructions=...,  # system prompt
            tools=[...],      # guarded_action, escalation, routing, clarification
        )
        self.language = language
```

### 6.2 BillingAgent — `agents/billing_agent.py`

Handles:
- Invoice inquiry (retrieves from context-service)
- Balance consultation
- Payment initiation (via execution-service → payment adapter)
- Payment deferral request (subject to policy rules: min 180 days, max 2/year, cap 200 TND)

### 6.3 TechnicalAgent — `agents/technical_agent.py`

Handles:
- SIM replacement (creates GLPI ticket via MCP)
- Network/connectivity issues
- SIM unblock/reactivate

### 6.4 AccountServicesAgent — `agents/account_services_agent.py`

Handles:
- Plan changes
- Top-up
- Roaming activation

### 6.5 ManagerAgent — `agents/manager_agent.py`

Target for human escalation. Used when:
- Caller frustration detected (sentiment score < -0.5)
- Identity verification fails
- Policy requires mandatory escalation
- Caller explicitly requests human

### 6.6 Base Agent — `agents/base_agent.py`

Shared logic:
- Tracks caller frustration level via `sentiment_history`
- Computes escalation trigger (frustration + identity gate)
- All agents use the same `guarded_action` tool facade

---

## 7. Tools — Guards

### 7.1 Guarded Action — `tools/guarded_action.py`

All sensitive operations go through this facade:

```
Caller request
    │
    ▼
GuardedAction tool
    │
    ├─► Identity verification (guards.identity_gate)
    ├─► DECISION_SERVICE — rank actions → confidence score
    ├─► POLICY_SERVICE  — deterministic rules → AUTHORIZED/REFUSED/ESCALATE
    └─► EXECUTION_SERVICE — dispatch if authorized
```

### 7.2 Guards — `tools/guards.py`

Identity verification gate. Must pass before sensitive actions (payment, SIM change, etc.)

### 7.3 Outcome Contract — `tools/outcomes.py`

Standardized response format for all tool outcomes:
- `success(data)` — action completed
- `refused(reason)` — policy refused
- `escalated(reason)` — needs human
- `clarification_needed(hint)` — ask caller for more info

### 7.4 Other Tools

| Tool | File | Purpose |
|---|---|---|
| `billing_tools` | `billing_tools.py` | Invoice, balance, payment, deferral |
| `technical_tools` | `technical_tools.py` | SIM ops, network diagnostics |
| `account_tools` | `account_tools.py` | Plan, top-up, roaming |
| `routing_tools` | `routing_tools.py` | Transfer to specialist agent |
| `escalation_tools` | `escalation_tools.py` | Transfer to manager agent |
| `clarification_tools` | `clarification_tools.py` | Ask caller for missing info |

---

## 8. Domain Services

All services use FastAPI, SQLAlchemy, and `service-auth` for internal API key auth.

### 8.1 context-service `:8101`

- `GET /customer/{msisdn}/snapshot` — Customer-360 (name, plan, balance, VIP flag, subscription_id, open tickets)
- `GET /customer/{msisdn}/invoices` — invoice history
- `GET /customer/{msisdn}/balance` — current balance
- `POST /customer/{msisdn}/verify-identity` — verify caller identity

### 8.2 knowledge-service `:8102`

- `GET /search?q=<query>` — RAG search (lexical + Qdrant vector hybrid)
- `POST /corpus/upload` — upload knowledge articles

### 8.3 decision-service `:8103`

- `POST /rank` — rank a list of candidate actions by confidence score
- Input: `{"candidate_actions": [...], "context": {...}}`
- Output: ranked list with confidence scores

### 8.4 policy-service `:8104`

Deterministic rules engine. Evaluates in fixed priority order:

1. **Mandatory escalation** — frustration, identity failure, high-risk operations
2. **Identity verification** — for sensitive actions
3. **Payment rules** — amount cap 200 TND
4. **Deferral rules** — min 180 days, max 2/year
5. **SIM rules** — unblock/replace/reactivate
6. **Outbound guardrails**

Returns: `AUTHORIZED` | `REFUSED(reason)` | `ESCALATE(reason)`

### 8.5 execution-service `:8105`

Idempotent action dispatcher. Routes to:
- `mock` adapter (dev — logs only)
- `live` adapter (production — calls real legacy systems)

Action types: send_sms, send_email, create_ticket, process_payment, etc.

### 8.6 notification-service `:8106`

- `POST /send/sms`
- `POST /send/whatsapp`
- `POST /send/email`

Uses Twilio (SMS/WhatsApp) and SendGrid (email) when keys are set, falls back to mock.

---

## 9. MCP Servers

All three use the Python `mcp` SDK (`mcp>=1.12,<2`) and expose tools via HTTP Streamable.

### 9.1 ai-knowledge-rag `:8201`

Tool: `knowledge_search(query: str)` → returns relevant knowledge chunks
Backend: Qdrant vector database + lexical search
Port: 8201

### 9.2 ticketing-glpi `:8202`

Tools: `create_ticket`, `get_ticket`, `update_ticket`, `close_ticket`
Backend: GLPI REST API (`GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`)
Port: 8202

### 9.3 messaging-gateway `:8203`

Tools: `send_sms`, `send_whatsapp`, `send_email`
Backend: notification-service
Port: 8203

**MCP Version Conflict**: `livekit-agents==1.6.3` uses `livekit/agents/llm/mcp.py` which calls `streamablehttp_client()` with an `http_client` kwarg that is **not accepted by `mcp>=1.12`** (the SDK changed the API). This causes `TypeError: streamablehttp_client() got an unexpected keyword argument 'http_client'`. **Fix: pin `mcp<1.12` or upgrade livekit-agents**.

---

## 10. Infrastructure

### 10.1 Docker Compose — Infra (`docker-compose.yml`)

Services started by `make infra`:
- `postgres:16` on 5432
- `redis:7.4` on 6379
- `qdrant:v1.12.5` on 6333
- `minio` on 9000/9001 (S3-compatible)
- `otel-collector` on 4317 (gRPC), 4318 (HTTP)

### 10.2 Docker Compose — Apps (`docker-compose.apps.yml`)

Services started by `make up` (combined with infra):
- All 6 domain services (8101–8106)
- `token-service` (8107)
- `business-api` (8108)
- `agent-worker`
- 3 MCP servers (8201–8203)

Build context is repo root. All services use `env_file: [.env]`.

### 10.3 Helm Charts

`infra/helm/telecom-platform/` deploys full stack to Kubernetes:
- Namespace: `telecom-platform`
- Infra: LiveKit server, Redis, Qdrant, MinIO, PostgreSQL
- Services: All 8 services + agent-worker
- Gateway: Nginx with routing rules
- OTEL: Collector deployment
- Secrets: API keys, database URL, LiveKit credentials

`deploy/helm/telecom-agent/` deploys just the agent-worker.

---

## 11. Docker Deployment

### 11.1 Build and Start

```bash
# From WSL/Git Bash:
make up              # build + start all containers (infra + apps)

# From PowerShell (no make):
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build

# Rebuild after code changes:
make rebuild         # stop + rebuild + start
```

### 11.2 Key Container Configuration

| Container | How to connect |
|---|---|
| `agent-worker` | Subscribes to LiveKit Cloud; connects to domain services via Docker DNS |
| `token-service` | REST API at `:8107` |
| `domain services` | REST APIs at `:8101`–`:8106` |
| `agent-worker` → domain services | Use Docker DNS names (e.g., `http://context-service:8101`) |

### 11.3 Key Environment Variables Inside Containers

```env
# Database
DATABASE_URL=postgresql+psycopg://telecom:telecom@postgres:5432/telecom

# LiveKit
LIVEKIT_URL=wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud
LIVEKIT_API_KEY=API4oF2JZPKv5s7
LIVEKIT_API_SECRET=K2vSLuHfjm5Psu95A7yuXUVnqGMR2qlWl1O6p0niSYE
LIVEKIT_AGENT_NAME=telecom-agent

# OTEL
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

---

## 12. CI/CD

### 12.1 GitHub Actions — `.github/workflows/ci.yml`

Pipeline stages (in order):
1. **lint** — Ruff lint + format check
2. **typecheck** — mypy strict
3. **test** — offline test suite via `scripts/run_tests.py`
4. **db-migrations** — `alembic upgrade head`
5. **docker-build** — builds all 12 Dockerfiles (9 services + 3 apps + agent-worker)
6. **docker-build-apps** — builds 3 frontend apps (supervisor-dashboard, client-widget, business-api)
7. **security-scan** — Trivy SARIF scan

Triggered on push to main and PRs.

---

## 13. Key Files Reference

### Agent Worker

| File | Purpose | Key Points |
|---|---|---|
| `src/server.py` | Composition root | Loads env, creates AgentServer, starts `entrypoint` |
| `src/config/settings.py` | 25+ env vars | `llm_primary_model=gemini-2.5-flash-latest` ⚠, `groq_model=llama3-8b-8192` ⚠ |
| `src/config/language_presets.py` | Per-language provider keys | All 6 keys present per language ✓ |
| `src/providers/llm.py` | LLM FallbackAdapter chain | `[gemini, nvidia, openai, groq]` |
| `src/providers/stt.py` | STT FallbackAdapter | Deepgram primary → Gladia → Azure |
| `src/providers/tts.py` | TTS FallbackAdapter | ElevenLabs primary → Cartesia → Azure |
| `src/providers/nvidia_adapter.py` | NVIDIA NIM LLM | Inherits `openai.LLM`, NIM base URL |
| `src/providers/groq_adapter.py` | Groq LLM | Inherits `openai.LLM`, Groq base URL |
| `src/providers/session_factory.py` | Assembles AgentSession | Wires STT/LLM/TTS/VAD/turn_detection |
| `src/providers/vad.py` | Silero VAD | Local CPU, no API key |
| `src/providers/turn_detection.py` | LiveKit MultilingualModel | ⚠ requires inference executor |
| `src/providers/_resilience.py` | Chaos toggle | `INVALID_MODEL=chaos-invalid-model-does-not-exist` |
| `src/agents/triage_agent.py` | Primary voice agent | Greets, routes, escalates |
| `src/tools/guarded_action.py` | D→P→E facade | All sensitive ops go through here |
| `src/tools/outcomes.py` | Standardized outcomes | success/refused/escalated/clarification |

### Configuration

| File | Purpose |
|---|---|
| `.env` | All env vars — API keys, model IDs, URLs |
| `apps/agent-worker/pyproject.toml` | `livekit-agents==1.6.3`, `mcp>=1.12,<2` |
| `infra/docker-compose/docker-compose.yml` | Infrastructure containers |
| `infra/docker-compose/docker-compose.apps.yml` | App containers + build |

### Error Investigation Reference

For the full error analysis, see `ERROR_INVESTIGATION.md`. Summary of the 6 root causes:

| # | Error | Source File | Fix |
|---|---|---|---|
| 1 | `gemini-2.5-flash-latest` → 404 | `settings.py:43` | Change to `gemini-3.5-flash` |
| 2 | `llama3-8b-8192` decommissioned | `settings.py:53` | Change to `llama-3.1-8b-instant` |
| 3 | OpenAI 429 quota exceeded | `.env:62` | Set `OPENAI_API_KEY=` (empty) or disable |
| 4 | NVIDIA API timeout | `nvidia_adapter.py` | Verify `NVIDIA_API_KEY` valid + key accessible |
| 5 | MCP `http_client` TypeError | `pyproject.toml:12` | Pin `mcp<1.12` |
| 6 | Turn detection no executor | `turn_detection.py` | Use Silero VAD instead, or configure LiveKit inference |

---

## 14. API Key Status

| Key | Status | Used By |
|---|---|---|
| `DEEPGRAM_API_KEY` | ✓ Live, working | STT (nova-3) |
| `GOOGLE_API_KEY` | ✓ Live | LLM primary — but model ID wrong (`gemini-2.5-flash-latest`) |
| `NVIDIA_API_KEY` | Configured | LLM fallback — timing out (key valid? endpoint accessible?) |
| `GROQ_API_KEY` | Configured | LLM fallback — model decommissioned |
| `OPENAI_API_KEY` | Configured | LLM fallback — quota exceeded (429) |
| `ELEVEN_API_KEY` | EMPTY | TTS primary — not working, no audio output |
| `CARTESIA_API_KEY` | ✓ Live | TTS fallback |
| `AZURE_SPEECH_KEY` | EMPTY | STT/TTS final fallback |
| `GLADIA_API_KEY` | ✓ Live | STT optional extra fallback |
| `GLPI_*` tokens | ✓ Live | Ticketing MCP server |

---

## 15. Known Configuration Issues

1. **`LLM_PRIMARY_MODEL=gemini-2.5-flash-latest`** — Google upgraded to Gemini 3.5 Flash. Model ID must change.
2. **`GROQ_MODEL=llama3-8b-8192`** — Groq decommissioned this model. Must use `llama-3.1-8b-instant`.
3. **`ELEVEN_API_KEY`** is empty — TTS primary is non-functional. No voice output possible without this or a fallback TTS.
4. **MCP version conflict** — `mcp>=1.12` is incompatible with `livekit-agents==1.6.3`'s use of `http_client` kwarg.
5. **OTEL collector** not running — trace export fails with `StatusCode.UNAVAILABLE`.
6. **Turn detection** requires LiveKit inference executor not available in Cloud — use Silero-based turn detection instead.