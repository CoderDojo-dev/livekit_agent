# Telecom AI Voice Agent Platform — Complete System Documentation

> **Purpose:** This file contains every configuration, script, source-code entrypoint, and architectural decision needed for an LLM to understand, debug, and extend the platform. No code has been modified to produce this document.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Tree](#2-directory-tree)
3. [Architecture & Design](#3-architecture--design)
4. [Environment Configuration (.env)](#4-environment-configuration-env)
5. [Build & Run System](#5-build--run-system)
6. [Docker Configuration](#6-docker-configuration)
7. [CI/CD Pipeline](#7-cicd-pipeline)
8. [Python Package Management](#8-python-package-management)
9. [Agent Worker — Core Pipeline](#9-agent-worker--core-pipeline)
10. [Domain Agents](#10-domain-agents)
11. [Provider Configuration (STT/LLM/TTS/VAD/Turn)](#11-provider-configuration)
12. [The Guarded Action Pipeline (Decision → Policy → Execution)](#12-the-guarded-action-pipeline)
13. [Microservices (6 domain services)](#13-microservices)
14. [MCP Servers (3 servers)](#14-mcp-servers)
15. [Frontend Applications](#15-frontend-applications)
16. [Telephony & SIP Transfer](#16-telephony--sip-transfer)
17. [Observability](#17-observability)
18. [Session State & Tools](#18-session-state--tools)
19. [Database Schema & Persistence](#19-database-schema--persistence)
20. [Security](#20-security)
21. [Deployment](#21-deployment)
22. [Documentation Index](#22-documentation-index)
23. [Known Issues & Open Items](#23-known-issues--open-items)

---

## 1. Project Overview

**Telecom AI Voice Agent Platform** — an AI-powered voice agent for a telecom operator's customer-support line. Built with Clean/Hexagonal Architecture + DDD + Event-Driven Microservices in a Python monorepo.

**Key numbers:**
- 10 shared Python packages
- 6 domain microservices (FastAPI, ports 8101–8106)
- 3 applications (token-service 8107, business-api 8108, agent-worker)
- 3 MCP servers (ports 8201–8203)
- 2 frontends (React 19 + Vite + TypeScript)
- 12 PostgreSQL schemas, 27 tables
- 6 Alembic migrations (reversible)
- 12 Dockerfiles + 8 docker-compose files
- Backed by PostgreSQL 16, Redis 7.4, Qdrant 1.12, MinIO, OpenTelemetry, Nginx
- Supports FR (primary) / AR / EN
- LiveKit Agents SDK 1.6.3 for real-time voice

---

## 2. Directory Tree

```
telecom-ai-agent-platform/
├── .env                          # 237 env vars across 25 sections (LIVE KEYS INCLUDED)
├── .env.example                  # Template with ⚠ markers for values that must be set
├── .gitignore
├── .dockerignore
├── Makefile                      # Unified dev orchestration (make dev = one-command startup)
├── Procfile                      # Honcho process definition for all 13+ local processes
├── start.ps1                     # PowerShell startup for full stack (up/down/rebuild/health)
├── pyproject.toml                # Root tooling config (ruff + mypy)
│
├── packages/                     # 10 shared Python packages (editable installs)
│   ├── domain-core/              # Pure entities/value objects/ports. Zero dependencies.
│   ├── persistence/              # SQLAlchemy 2.0 models + engine + Alembic migrations (27 tables)
│   ├── audit-trail/              # Hash-chained append-only audit ledger
│   ├── pii-shield/               # PII detection/masking/pseudonymization
│   ├── service-auth/             # X-API-Key inter-service auth (FastAPI dep + httpx client)
│   ├── observability-kit/        # OpenTelemetry tracer/meter setup
│   ├── cache/                    # Optional Redis cache (NullCache fallback)
│   ├── object-storage/           # Optional MinIO/S3 (NullStore fallback)
│   ├── notification-client/      # SMS/Email/WhatsApp abstraction (Strategy pattern)
│   └── integration-adapters/     # Per-legacy-system adapters (mock by default)
│
├── services/                     # 6 domain microservices
│   ├── context-service/          # Customer-360, identity resolution, invoices, balance (8101)
│   ├── knowledge-service/        # RAG over documentation corpus + Qdrant vector store (8102)
│   ├── decision-service/         # Candidate-action ranking + confidence scoring (8103)
│   ├── policy-service/           # Deterministic policy engine — AUTHORIZED/REFUSED/ESCALATE (8104)
│   ├── execution-service/        # Idempotent action dispatch with hash-chain audit (8105)
│   └── notification-service/     # Outbound SMS/Email/WhatsApp via templates FR/AR/EN (8106)
│
├── apps/                         # 3 applications
│   ├── agent-worker/             # LiveKit Agents real-time orchestrator (the core pipeline)
│   │   └── src/
│   │       ├── server.py         # Composition root — wires everything
│   │       ├── agents/           # Domain personas (6 agents)
│   │       │   ├── base_agent.py           # BaseTelecomAgent (sentiment + logging + de-escalation)
│   │       │   ├── triage_agent.py         # TriageAgent: consent, greet, route, escalate
│   │       │   ├── billing_agent.py        # BillingAgent: invoices, payments, deferrals
│   │       │   ├── technical_agent.py      # TechnicalAgent: SIM, network, tickets
│   │       │   ├── account_services_agent.py # AccountServicesAgent: plans, recharge, roaming
│   │       │   └── manager_agent.py        # ManagerAgent: escalation target
│   │       ├── providers/        # Vendor boundary — LiveKit plugin wrappers
│   │       │   ├── stt.py                  # STT builder (Deepgram → Gladia → Azure)
│   │       │   ├── tts.py                  # TTS builder (ElevenLabs → Cartesia → Azure)
│   │       │   ├── llm.py                  # LLM builder (Gemini → NVIDIA → OpenAI → Groq)
│   │       │   ├── vad.py                  # Silero VAD
│   │       │   ├── turn_detection.py       # Turn detection
│   │       │   ├── nvidia_adapter.py       # NVIDIA NIM LLM adapter
│   │       │   ├── groq_adapter.py         # Groq LLM adapter
│   │       │   ├── session_factory.py      # AgentSession assembly
│   │       │   ├── noise_cancellation.py   # BVC noise cancellation
│   │       │   ├── language_router.py      # Per-language routing
│   │       │   └── _resilience.py         # Chaos model helper
│   │       ├── clients/          # Typed HTTP clients to microservices
│   │       │   ├── context_client.py       # Context service client
│   │       │   ├── decision_client.py      # Decision service client
│   │       │   ├── policy_client.py        # Policy service client
│   │       │   ├── execution_client.py     # Execution service client
│   │       │   ├── notification_client.py  # Notification service client
│   │       │   └── routing_client.py       # Advisor routing client
│   │       ├── mcp_clients/      # MCP toolset clients
│   │       │   ├── knowledge_toolset.py    # Knowledge search MCP
│   │       │   └── ticketing_toolset.py    # GLPI ticketing MCP
│   │       ├── tools/            # LLM-callable function tools
│   │       │   ├── guarded_action.py       # Decision → Policy → Execution façade
│   │       │   ├── guards.py              # ensure_identity_verified
│   │       │   ├── outcomes.py            # Standard outcome contract
│   │       │   ├── routing_tools.py       # route_to_billing, route_to_technical
│   │       │   ├── escalation_tools.py    # escalate_to_manager
│   │       │   ├── clarification_tools.py # request_clarification
│   │       │   ├── billing_tools.py       # get_invoice_summary, get_balance_summary
│   │       │   ├── account_tools.py       # get_plan_details, change_plan, top_up, toggle_roaming
│   │       │   └── technical_tools.py     # Stubs (Phase 5/7/8)
│   │       ├── tasks/            # AgentTask subclasses (inline sub-agents)
│   │       │   ├── consent_task.py                # Recording consent collection
│   │       │   ├── identity_verification_task.py   # Step-up identity verification
│   │       │   ├── payment_confirm_task.py         # Payment amount confirmation
│   │       │   ├── callback_schedule_task.py       # Callback scheduling
│   │       │   └── sim_replacement_task_group.py   # Multi-step SIM replacement (stub)
│   │       ├── session/          # Session state
│   │       │   ├── user_data.py           # Legacy SessionUserData
│   │       │   ├── session_state.py       # Current SessionUserData (dataclass)
│   │       │   └── customer_context.py    # CustomerContext dataclass
│   │       ├── conversation/     # Durable conversation record
│   │       │   └── writer.py             # Non-blocking conversation DB writer
│   │       ├── sentiment/        # Sentiment scoring
│   │       │   └── sentiment_scorer.py   # Deterministic lexical scorer
│   │       ├── observability/    # Observability wiring
│   │       │   ├── log_masking.py        # PII logging filter
│   │       │   ├── metrics_hook.py       # TTFA/TTFT metrics + OTel export
│   │       │   └── metrics_hooks.py      # Stub for Phase 3/11
│   │       ├── telephony/        # Telephony features
│   │       │   └── sip_transfer.py       # SIP transfer + callback fallback
│   │       ├── config/           # Configuration
│   │       │   ├── settings.py           # Pydantic Settings (reads from .env)
│   │       │   └── language_presets.py    # Per-language provider config + greetings
│   │       └── entrypoints/      # Alternate entrypoints
│   │           └── worker.py
│   ├── token-service/            # LiveKit JWT minting (8107)
│   └── business-api/             # Back-office REST API with RBAC (8108)
│
├── mcp-servers/                  # 3 MCP servers (Model Context Protocol)
│   ├── ai-knowledge-rag/        # Knowledge search (RAG/FAQ), read-only (8201)
│   ├── ticketing-glpi/          # GLPI ticket lifecycle (8202)
│   └── messaging-gateway/       # Outbound SMS/WhatsApp placeholder (8203)
│
├── infra/
│   ├── docker-compose/
│   │   ├── docker-compose.yml    # Infra stack (Postgres, Redis, Qdrant, MinIO, LiveKit, OTel)
│   │   ├── docker-compose.apps.yml # App containers (all 8 services + 3 MCP + worker)
│   │   └── nginx/nginx.conf     # Full API gateway config
│   └── helm/telecom-platform/   # Kubernetes Helm chart
│
├── deploy/
│   ├── postgres/docker-compose.yml       # Postgres 16 standalone
│   ├── otel/docker-compose.yml           # OTel collector + Prometheus
│   ├── otel/otel-collector-config.yaml   # OTel pipeline config
│   ├── otel/prometheus.yml               # Prometheus scrape config
│   ├── gateway/docker-compose.gateway.yml # Nginx gateway
│   ├── gateway/nginx.conf                # Production gateway config
│   ├── secrets/docker-compose-secrets.yml
│   ├── backup/backup.sh                  # pg_dump nightly backup
│   └── backup/restore.sh                 # pg_restore
│
├── scripts/
│   ├── run_tests.py             # Offline test suite runner with PYTHONPATH
│   ├── health_check.py          # Probe every service /health
│   ├── install_dev.ps1          # Install all packages/services/tools in order
│   ├── start_dev.ps1            # Start infra + migrate + seed + honcho
│   ├── start_dev_containers.ps1 # Build + run everything in containers
│   ├── stop_dev.ps1             # Stop all containers
│   └── fix_frontend_deps.sh     # Fix frontend deps for Linux/WSL
│
├── docs/
│   ├── RUN.md                   # Running the platform
│   ├── AI_MODEL_INVENTORY.md    # Full model inventory (280 lines)
│   ├── architecture/            # Architecture docs + DR-0 decision record
│   ├── phase-7/                 # Execution & Sensitive Actions
│   ├── phase-8/                 # Sentiment & Escalation
│   ├── phase-9/                 # Ticketing & Notifications
│   ├── phase-10/                # Frontend
│   ├── phases/                  # Phases 11-12
│   ├── persistence/             # P1-P6 data layer docs + ADR
│   ├── patches/                 # All patch-set docs + diagnostics
│   └── compliance/              # Pilot readiness, traceability, UAT plan
│
├── tests/load/                  # Load testing (soak.py, loadtest.py)
├── fixes/                       # Diagnostic fix copies
└── .github/workflows/ci.yml     # GitHub Actions (lint → test → db-migrations → docker → security-scan)
```

---

## 3. Architecture & Design

### 3.1 High-Level Architecture

```
                   ┌──────────────┐
                   │   Browser    │
                   │ (Client      │
                   │  Widget)     │
                   └──────┬───────┘
                          │ HTTP/WSS
                   ┌──────▼───────┐     ┌─────────────────┐
                   │ token-service │     │ Supervisor      │
                   │  (JWT mint)   │     │ Dashboard       │
                   └──────┬───────┘     └────────┬────────┘
                          │ LiveKit Cloud         │ HTTP
                   ┌──────▼──────────────────────▼────────┐
                   │         Nginx API Gateway            │
                   │  (only token & business-api public)  │
                   └──────┬───────────────────────────────┘
                          │
        ┌─────────────────┼────────────────────┐
        │                 │                     │
  ┌─────▼──────┐   ┌─────▼──────┐   ┌─────────▼──────────┐
  │ LiveKit    │   │ Agent      │   │ business-api        │
  │ Cloud/Self │   │ Worker     │   │ (Back-office REST)  │
  │ -hosted    │   │(Voice      │   │ :8108               │
  │ :7880      │   │ Pipeline)  │   │                     │
  └────────────┘   └─────┬──────┘   └─────────────────────┘
                         │ Internal network (INTERNAL_API_KEY)
           ┌─────────────┼──────────────────────────────┐
           │             │                              │
     ┌─────▼────┐  ┌─────▼────┐                   ┌────▼────┐
     │ Context  │  │ Decision │  ... 6 services   │ Notif.  │
     │ :8101    │  │ :8103    │   8101-8106        │ :8106   │
     └──────────┘  └──────────┘                   └─────────┘
           │             │                              │
     ┌─────▼────┐  ┌─────▼────┐                   ┌────▼────┐
     │ Postgres │  │ Qdrant   │    Infra           │ Redis   │
     │ :5432    │  │ :6333    │    (containers)    │ :6379   │
     └──────────┘  └──────────┘                   └─────────┘
```

### 3.2 Layered Architecture

| Layer | Components |
|-------|-----------|
| **Voice Pipeline** (agent-worker) | STT (Deepgram→Gladia→Azure), LLM (Gemini→NVIDIA→OpenAI→Groq), TTS (ElevenLabs→Cartesia→Azure), VAD (Silero), Turn Detection (STT-based) |
| **6 Domain Microservices** | context (8101), knowledge (8102), decision (8103), policy (8104), execution (8105), notification (8106) |
| **3 MCP Servers** | ai-knowledge-rag (8201), ticketing-glpi (8202), messaging-gateway (8203) |
| **3 Apps** | token-service (8107), business-api (8108), agent-worker (LiveKit agent) |
| **2 Frontends** | client-widget (React 19 + Vite + TS, :5173), supervisor-dashboard (React 19 + Vite + TS, :5174) |
| **10 Shared Packages** | domain-core, persistence, audit-trail, pii-shield, service-auth, observability-kit, cache, object-storage, notification-client, integration-adapters |
| **Infrastructure** | PostgreSQL 16, Redis 7.4, Qdrant 1.12, MinIO, LiveKit server, OTel Collector, Prometheus, Nginx |

### 3.3 Data Flow for a Voice Call

```
1. Browser → token-service → gets LiveKit JWT + room URL
2. Browser joins LiveKit room (WebRTC)
3. LiveKit Cloud dispatches the agent-worker via agent dispatch
4. AgentServer.rtc_session() entrypoint fires:
   a. Configure OTel tracer
   b. build_agent_session() → wires STT/LLM/TTS/VAD/TurnDetection
   c. Pre-fetch caller context from context-service (Customer-360 via MSISDN)
   d. Open conversation record (ConversationWriter — async DB writer)
   e. Start TriageAgent session
5. TriageAgent (LLM) processes turns:
   a. Per-turn: BaseTelecomAgent.on_user_turn_completed() → sentiment score + log
   b. LLM decides: answer FAQ (knowledge_search MCP), route (billing/technical), escalate
6. Sensitive actions go through the Guarded Action Pipeline:
   a. Identity verification (if not verified)
   b. Decision service → recommend action + confidence
   c. Policy service → AUTHORIZED/REFUSED/ESCALATE (deterministic rules)
   d. If AUTHORIZED → Execution service → idempotent dispatch + audit
7. Conversation ends → finish_session() records duration, disposition, max frustration
```

---

## 4. Environment Configuration (.env)

The `.env` file contains **237 variables across 25 sections**. Every variable is read by at least one module. The `.env.example` is the single source of truth.

### 4.1 Section Overview

| # | Section | Key Variables |
|---|---------|--------------|
| 1 | DATABASE | `DATABASE_URL`, `DB_POOL_SIZE`, `POSTGRES_*` |
| 2 | CONNECTOR_MODE | `CONNECTOR_MODE=mock\|live` |
| 3 | SERVICE AUTH | `INTERNAL_API_KEY` (unset = disabled in dev) |
| 4 | CORS | `CORS_ORIGINS` |
| 5 | LIVEKIT | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| 6 | VOICE/LLM PROVIDERS | `DEEPGRAM_API_KEY`, `GOOGLE_API_KEY`, `ELEVEN_API_KEY`, `CARTESIA_API_KEY`, `AZURE_SPEECH_KEY`, `NVIDIA_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `GLADIA_API_KEY` |
| 7 | MODEL SELECTION | `STT_MODEL`, `TTS_MODEL`, `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, `NVIDIA_MODEL`, `GROQ_MODEL`, `CARTESIA_TTS_MODEL` |
| 8 | VAD/TURN/LATENCY | `VAD_MIN_SILENCE`, `PREEMPTIVE_GENERATION`, `NOISE_CANCELLATION`, `DECISION_CONFIDENCE_THRESHOLD` |
| 9 | CHAOS/RESILIENCE | `CHAOS_BREAK_STT`, `CHAOS_BREAK_LLM`, `CHAOS_BREAK_TTS` |
| 10 | LANGUAGE | `SUPPORTED_LANGUAGES`, `DEFAULT_LANGUAGE`, `SESSION_LANGUAGE`, `SESSION_CALLER_MSISDN` |
| 11 | SERVICE URLs | `CONTEXT_SERVICE_URL` through `NOTIFICATION_SERVICE_URL` |
| 12 | MCP URLs | `KNOWLEDGE_MCP_URL`, `TICKETING_MCP_URL`, `MESSAGING_MCP_URL` |
| 13 | MCP HOST/PORT | `MCP_HOST`, `MCP_PORT` (per-server) |
| 14 | GLPI | `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` |
| 15 | MESSAGING | `TWILIO_*`, `SENDGRID_API_KEY`, `SMTP_*` |
| 16 | LEGACY ADAPTERS | `OCS_ADAPTER_URL`, `BILLING_ADAPTER_URL`, `PAYMENT_ADAPTER_URL`, `CRM_ADAPTER_URL`, `NMS_ADAPTER_URL`, `PROVISIONING_ADAPTER_URL`, `GLPI_ADAPTER_URL` |
| 17 | RAG | `QDRANT_URL`, `QDRANT_COLLECTION`, `EMBEDDING_MODEL` |
| 18 | CACHE | `REDIS_URL`, `CACHE_TTL_SECONDS` |
| 19 | OBJECT STORAGE | `MINIO_*` |
| 20 | OBSERVABILITY | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` |
| 21 | POLICY THRESHOLDS | `POLICY_PAYMENT_CAP_TND`, `POLICY_DEFERRAL_*` |
| 22 | BUSINESS API | `BUSINESS_API_DEFAULT_ROLE` |
| 23 | BACKUP | `BACKUP_DIR` |
| 24 | LOGGING | `LOG_LEVEL` |
| 25 | FRONTENDS | `VITE_TOKEN_URL`, `VITE_BUSINESS_API_URL`, `VITE_API_ROLE` |

### 4.2 Key Live Credentials (from current .env)

- LiveKit Cloud: `wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud`
- Deepgram API Key: Present (STT primary)
- Google Gemini API Key: Present (LLM primary)
- Cartesia API Key: `sk_car_tofNa8mAPgQWd7uVqEiQom` (TTS fallback)
- NVIDIA API Key: Present (LLM fallback)
- Groq API Key: Present (LLM fallback)
- Gladia API Key: Present (STT fallback)
- GLPI: Connected to `https://voiceagentai.fr33.glpi-network.cloud`
- ElevenLabs: Key EMPTY (TTS primary is effectively Cartesia)
- Azure Speech: Key EMPTY (fallback unconfigured)
- OpenAI: Key present but `OPENAI_ENABLED=false` (quota exhausted)
- Twilio/SendGrid/SMTP: All EMPTY (mock mode)

---

## 5. Build & Run System

### 5.1 Makefile (74 lines)

```makefile
SHELL := /bin/bash
PACKAGES := domain-core persistence audit-trail pii-shield observability-kit service-auth cache object-storage notification-client integration-adapters
SERVICES := services/context-service services/knowledge-service services/decision-service services/policy-service services/execution-service services/notification-service apps/token-service apps/business-api
MCP := mcp-servers/ai-knowledge-rag mcp-servers/ticketing-glpi mcp-servers/messaging-gateway
```

**Targets:**
- `make dev` — ONE COMMAND: install + infra + migrate + seed + honcho start
- `make install` — Install all packages in correct order + services + MCP + honcho
- `make frontends` — npm install both web apps
- `make infra` — Start Postgres/Redis/Qdrant/MinIO/OTel containers
- `make infra-livekit` — Also start self-hosted LiveKit server
- `make migrate` — Alembic upgrade head
- `make seed` — Seed pilot callers + reference catalogs
- `make up` — All containers (infra + apps)
- `make down` — Stop everything
- `make rebuild` — Stop → rebuild → restart (after code changes)
- `make health` — Probe every /health
- `make test` — Run the offline test suite
- `make live-logs` — Follow token-service + agent-worker logs

### 5.2 Procfile (16 lines)

```
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

### 5.3 PowerShell Scripts

#### start.ps1 (80 lines)
```powershell
param([string]$Command = "help")
switch ($Command) {
    "up"     { docker compose -f $F -f $A up -d }
    "down"   { docker compose -f $F -f $A --profile self-hosted-livekit down }
    "rebuild"{ docker compose -f $F -f $A up -d --build }
    "build"  { docker compose -f $F -f $A build }
    "logs"   { docker compose -f $F -f $A logs -f --tail=120 token-service agent-worker }
    "status" { docker compose -f $F -f $A ps }
    "health" { # Probes all 8 services on ports 8101-8108 }
}
```

#### scripts/install_dev.ps1 (59 lines)
Installs in order: 10 shared packages → 8 services → 3 MCP servers → agent-worker → honcho → frontends.

#### scripts/start_dev.ps1 (39 lines)
Start infra containers → wait for postgres → apply migrations → seed data → honcho start.

#### scripts/start_dev_containers.ps1 (27 lines)
Container-only path: docker compose up -d --build → wait for postgres → run migrations inside context-service.

#### scripts/stop_dev.ps1 (10 lines)
`docker compose ... down`

### 5.4 Shell Scripts

#### scripts/fix_frontend_deps.sh (13 lines)
Reinstalls frontend node_modules for Linux/WSL (rm -rf + npm ci).

#### deploy/backup/backup.sh (15 lines)
Nightly pg_dump with 14-day retention: `pg_dump --format=custom --no-owner`.

#### deploy/backup/restore.sh (8 lines)
`pg_restore --clean --if-exists --no-owner`.

### 5.5 Test Runner (scripts/run_tests.py, 54 lines)

Runs pytest across 14 targets with correct PYTHONPATH:
- packages/audit-trail, service-auth, cache, object-storage, integration-adapters, persistence, observability-kit
- services/context-service, knowledge-service, policy-service, execution-service, notification-service
- mcp-servers/ticketing-glpi
- apps/business-api

### 5.6 Health Check (scripts/health_check.py, 58 lines)

Probes 8 HTTP services (/health on ports 8101-8108) + 3 TCP MCP servers (ports 8201-8203).

---

## 6. Docker Configuration

### 6.1 Dockerfiles (12 total — all share the same pattern)

All 12 Dockerfiles follow this pattern:
```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY <service> ./<service>/
RUN pip install ./<service>
USER app
EXPOSE <port>
HEALTHCHECK ... (for HTTP services)
CMD [...]
```

**Services** (all use uvicorn on port):
- context-service:8101, knowledge-service:8102, decision-service:8103
- policy-service:8104, execution-service:8105, notification-service:8106
- token-service:8107, business-api:8108

**MCP servers** (all use python -m):
- ai-knowledge-rag:8201, ticketing-glpi:8202, messaging-gateway:8203

**Agent worker** (special — downloads models at build time):
```dockerfile
USER app
RUN python -m livekit.agents download-files
CMD ["python", "apps/agent-worker/src/server.py", "start"]
```

### 6.2 Docker Compose — Infra Stack (docker-compose.yml, 77 lines)

| Service | Image | Ports |
|---------|-------|-------|
| livekit-server | livekit/livekit-server:v1.8.4 | 7880-7882 (opt-in profile) |
| redis | redis:7.4-alpine | 6379 |
| postgres | postgres:16-alpine | 5432 |
| qdrant | qdrant/qdrant:v1.12.5 | 6333 |
| minio | minio/minio:RELEASE.2024-12-18 | 9000, 9001 |
| otel-collector | otel/opentelemetry-collector-contrib:0.116.1 | 4317, 4318 |

Volumes: postgres-data, minio-data

### 6.3 Docker Compose — Apps (docker-compose.apps.yml, 125 lines)

All 12 app containers. Each:
- Builds from repo root with context: ../..
- Uses the per-service Dockerfile
- Reads .env file
- Overrides DATABASE_URL for Docker DNS (postgres:5432)
- Restarts unless-stopped

### 6.4 Nginx Gateway

**Production config** (deploy/gateway/nginx.conf, 35 lines):
- Only exposes token-service (:8107) and business-api (:8108)
- 6 internal services are NOT exposed (private network behind INTERNAL_API_KEY)
- TLS terminates here in staging/prod

**Full gateway** (infra/docker-compose/nginx/nginx.conf, 118 lines):
- Exposes all 8 services + LiveKit WebSocket proxy + MinIO
- Security headers on every response

---

## 7. CI/CD Pipeline

### .github/workflows/ci.yml (165 lines)

**Jobs (sequential):**
1. **lint** — ruff check + mypy (soft-fail with `|| true`)
2. **test** — Install shared packages → pytest per package/service (hard-fail with `set -e`)
3. **db-migrations** — Spin up Postgres 16 → apply Alembic → seed pilot + reference data
4. **docker-build** — Build + push all 9 service images to ghcr.io (main branch only)
5. **docker-build-apps** — Build + push 3 app images (token-service, business-api, agent-worker)
6. **security-scan** — Trivy vulnerability scanner on all 9 images, upload SARIF to GitHub CodeQL

Registry: `ghcr.io/${{ github.repository }}`
Image tags: `${{ github.sha }}` + `latest`

---

## 8. Python Package Management

### 8.1 Root pyproject.toml (23 lines)

Only tooling config (ruff + mypy). No build target at root.

```toml
[tool.ruff]
target-version = "py312"
line-length = 110
extend-exclude = ["**/alembic/versions/*", "**/node_modules/**", "**/dist/**", "fixes/**"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["persistence", "audit_trail", "domain_core", ...]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
```

### 8.2 Shared Packages (10)

| Package | Dependencies | Description |
|---------|-------------|-------------|
| **domain-core** | none | Pure entities/value objects/ports. Zero framework dependencies |
| **persistence** | sqlalchemy>=2.0, psycopg[binary], alembic>=1.13 | Shared SQLAlchemy 2.0 models, engine/session, Alembic migrations |
| **audit-trail** | domain-core, persistence | Append-only, hash-chained audit ledger (in-memory + Postgres) |
| **pii-shield** | none | PII detection/masking/pseudonymization |
| **service-auth** | fastapi | X-API-Key inter-service auth (FastAPI dep + httpx client headers) |
| **observability-kit** | opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc | Shared OTel tracer/meter setup + metric naming conventions |
| **cache** | redis>=5.0 | Optional Redis cache (NullCache fallback when Redis unavailable) |
| **object-storage** | minio>=7.2 | Optional MinIO/S3 object storage (NullStore fallback) |
| **notification-client** | httpx==0.28.1, domain-core | SMS/Email/WhatsApp abstraction (Strategy over channels) |
| **integration-adapters** | domain-core, httpx==0.28.1 | Per-legacy-system adapters (OCS, Billing, Payment, CRM, NMS, Provisioning, GLPI) |

### 8.3 Services (6)

| Service | Key Dependencies | Console Script | Port |
|---------|-----------------|----------------|------|
| context-service | sqlalchemy, cache, service-auth, persistence | `context-service` | 8101 |
| knowledge-service | httpx, service-auth, domain-core | `knowledge-service` | 8102 |
| decision-service | service-auth, domain-core | `decision-service` | 8103 |
| policy-service | sqlalchemy, service-auth, audit-trail, persistence | `policy-service` | 8104 |
| execution-service | sqlalchemy, integration-adapters, service-auth, audit-trail, persistence | `execution-service` | 8105 |
| notification-service | service-auth, persistence, pii-shield | `notification-service` | 8106 |

### 8.4 Apps (3)

| App | Key Dependencies | Console Script | Port |
|-----|-----------------|----------------|------|
| agent-worker | livekit-agents==1.6.3, mcp>=1.9, pydantic==2.10.4, httpx==0.28.1, structlog==24.4.0 | None (python server.py) | — |
| token-service | fastapi==0.115.6, uvicorn==0.34.0, livekit-api>=0.8 | `token-service` | 8107 |
| business-api | sqlalchemy, fastapi==0.115.6, audit-trail, persistence, object-storage | `business-api` | 8108 |

### 8.5 MCP Servers (3)

| Server | Dependencies | Console Script | Port |
|--------|-------------|----------------|------|
| ai-knowledge-rag | mcp>=1.0.0, httpx==0.28.1 | `ai-knowledge-rag` | 8201 |
| ticketing-glpi | persistence, mcp>=1.0.0, httpx==0.28.1 | `ticketing-glpi` | 8202 |
| messaging-gateway | mcp, httpx==0.28.1 | `messaging-gateway` | 8203 |

---

## 9. Agent Worker — Core Pipeline

### 9.1 Composition Root (apps/agent-worker/src/server.py)

The `server.py` is the **composition root** — it wires everything together:
1. Create `AgentServer` (optional agent_name for room dispatch)
2. Register RTC session entrypoint
3. Entrypoint flow:
   - Configure OTel tracer
   - Build AgentSession (STT/LLM/TTS/VAD/TurnDetection via session_factory)
   - Pre-fetch caller context from context-service (Customer-360 snapshot)
   - Open ConversationWriter (non-blocking DB writer off the voice path)
   - Register shutdown callbacks (finish session, attach metrics)
   - Register debug event listeners (user_speech, agent_speech, function_calls)
   - Build optional noise cancellation
   - Start TriageAgent session

```python
@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    configure_tracer("agent-worker")
    session = build_agent_session(settings, language)
    user_data = await _prefetch_user_data(language)
    session.userdata = user_data
    writer = _open_conversation(ctx, user_data)
    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(attach_metrics(session))
    await session.start(agent=TriageAgent(language=language), room=ctx.room)
```

### 9.2 Session Factory (providers/session_factory.py)

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

### 9.3 Settings (config/settings.py)

Pydantic `BaseSettings` loaded from `.env`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    # 45+ fields across: LiveKit, language, STT/TTS/LLM models, VAD, chaos, service URLs, MCP URLs, thresholds
```

Key behavior:
- `@lru_cache` on `get_settings()` — singleton, loaded once
- All env vars have sensible defaults for local dev
- Service URLs are overridable for Docker compose (use DNS names)

---

## 10. Domain Agents

### 10.1 BaseTelecomAgent (agents/base_agent.py)

Every persona inherits from `BaseTelecomAgent` (extends `livekit.agents.Agent`):

```python
class BaseTelecomAgent(Agent):
    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        # 1. Score sentiment (LexicalSentimentScorer)
        # 2. Record turn + sentiment to conversation DB (off-path)
        # 3. Inject de-escalation note if frustration is high
```

**Key behavior:**
- Scores every caller turn for sentiment (frustration detection)
- Records transcript (PII-masked) + sentiment to durable conversation log
- Injects proactive de-escalation note when `should_offer_escalation` is True

### 10.2 TriageAgent (agents/triage_agent.py)

The **default starting persona** — first point of contact.

```python
class TriageAgent(BaseTelecomAgent):
    async def on_enter(self):
        # 1. Collect recording consent (ConsentTask)
        # 2. Greet caller by name (personalized if CustomerContext exists)
```

**Tools:** request_clarification, route_to_billing, route_to_technical, escalate_to_manager, knowledge_search

**Instructions:** Greet, determine need, answer FAQs (via knowledge_search), route to specialist, escalate to human. Reply in caller's language.

### 10.3 BillingAgent (agents/billing_agent.py)

Handles billing/payment/risk. Created via `route_to_billing` tool.

**Read tools (no policy check):** get_invoice_summary, get_balance_summary
**Write tools (guarded):** make_payment (amount confirm → Decision → Policy → Execution), request_payment_deferral

### 10.4 TechnicalAgent (agents/technical_agent.py)

Handles SIM/network/connectivity. Created via `route_to_technical` tool.

**Tools:** unblock_sim (identity-gated + guarded), knowledge_search, escalate_to_manager, ticketing (create/resolve ticket)

### 10.5 AccountServicesAgent (agents/account_services_agent.py)

Handles plans/recharge/roaming (lower risk).

**Tools:** get_plan_details (read), change_plan, top_up, toggle_roaming (all guarded writes)

### 10.6 ManagerAgent (agents/manager_agent.py)

**Escalation target** — reached on shared session (full context).

**Tools:** transfer_to_human (SIP transfer or callback), ticketing (create ticket for tracking)

---

## 11. Provider Configuration

### 11.1 STT Builder (providers/stt.py)

```python
def build_stt(preset, model="nova-3", break_primary=False):
    # Primary: deepgram.STT (DEEPGRAM_API_KEY)
    providers = [deepgram.STT(model=chaos_model(model, break_primary), language=preset["deepgram_language"])]
    # Fallback 1: gladia.STT (skipped if GLADIA_API_KEY absent)
    if gladia_key: providers.append(gladia.STT(languages=[preset["gladia_language"]], api_key=gladia_key))
    # Fallback 2: azure.STT (skipped if AZURE_SPEECH_KEY absent)
    if azure_key: providers.append(azure.STT(language=preset["azure_stt_locale"]))
    return stt_module.FallbackAdapter(providers)
```

**Chain:** Deepgram (primary) → Gladia (optional) → Azure (optional)
**Arabic:** routes to Deepgram `language="ar"` (monolingual model, never `"multi"`)

### 11.2 TTS Builder (providers/tts.py)

```python
def build_tts(preset, model, voice_id, break_primary=False):
    providers = []
    # Primary: elevenlabs.TTS (skipped if ELEVEN_API_KEY absent)
    if eleven_key: providers.append(elevenlabs.TTS(model=chaos_model(model, break_primary), voice_id=voice_id, language=preset["tts_iso"]))
    # Fallback: cartesia.TTS (skipped if CARTESIA_API_KEY absent)
    if cartesia_key: providers.append(cartesia.TTS(model=..., voice=preset["cartesia_voice_id"], api_key=cartesia_key))
    return tts_module.FallbackAdapter(providers)
```

**Chain:** ElevenLabs (primary, key EMPTY) → Cartesia (fallback, key present)
**Note:** Deepgram TTS is NOT available in livekit-agents==1.6.3

### 11.3 LLM Builder (providers/llm.py)

```python
def build_llm(primary_model, fallback_model, break_primary=False):
    providers = [google.LLM(model=chaos_model(primary_model, break_primary))]
    # Fallback 2: NvidiaLLM (NVIDIA_API_KEY)
    if nvidia_key: providers.append(NvidiaLLM(api_key=nvidia_key, model=nvidia_model, timeout=nvidia_timeout))
    # Fallback 3: openai.LLM (OPENAI_API_KEY + OPENAI_ENABLED)
    if openai_key and openai_enabled: providers.append(openai.LLM(model=fallback_model))
    # Fallback 4: GroqLLM (GROQ_API_KEY)
    if groq_key: providers.append(GroqLLM(api_key=groq_key, model=groq_model, timeout=groq_timeout))
    return llm_module.FallbackAdapter(providers, attempt_timeout=12.0)
```

**Chain:** Google Gemini 2.5 Flash (primary) → NVIDIA NIM (optional) → OpenAI GPT (optional, disabled) → Groq (optional)

### 11.4 VAD Builder (providers/vad.py)

```python
def build_vad(min_silence=0.25):
    return silero.VAD.load(min_silence_duration=min_silence)
```

### 11.5 Turn Detection (providers/turn_detection.py)

Returns `"stt"` — uses STT-based turn detection.

### 11.6 NVIDIA NIM Adapter (providers/nvidia_adapter.py)

Subclasses `livekit.plugins.openai.LLM` with `base_url="https://integrate.api.nvidia.com/v1"`.

### 11.7 Groq Adapter (providers/groq_adapter.py)

Subclasses `livekit.plugins.openai.LLM` with `base_url="https://api.groq.com/openai/v1"`.

### 11.8 Resilience Helper (providers/_resilience.py)

```python
INVALID_MODEL = "chaos-invalid-model-does-not-exist"
def chaos_model(real_model, break_primary):
    return INVALID_MODEL if break_primary else real_model
```

---

## 12. The Guarded Action Pipeline

Every sensitive action flows through **Decision → Policy → Execution** (never bypassable).

### 12.1 Guarded Action (tools/guarded_action.py)

```python
async def execute_guarded_action(run_context, action_type, payload):
    context = _build_context(run_context, action_type, payload)
    # 1. Decision → recommend action + confidence
    decision = await get_decision_client().recommend(action_type, context)
    if decision["confidence"] < threshold: return outcomes.escalate(...)
    # 2. Policy → binding verdict (AUTHORIZED/REFUSED/ESCALATE)
    verdict = await get_policy_client().evaluate_action(context)
    if verdict["verdict"] == "refused": return outcomes.refused(...)
    if verdict["verdict"] == "escalate": return outcomes.escalate(...)
    # 3. Execution → idempotent dispatch
    return await get_execution_client().execute(...)
```

### 12.2 Policy Engine (services/policy-service/src/policy_service/engine.py)

**Deterministic, pure functions — no I/O.**

```python
SENSITIVE_ACTIONS = frozenset({
    "EXECUTE_PAYMENT", "PAYMENT_DEFERRAL", "UNBLOCK_SIM",
    "REPLACE_SIM", "REACTIVATE_SIM", "TOP_UP", "CHANGE_PLAN", "ACTIVATE_ROAMING"
})
```

**Evaluation order:**
1. **Mandatory escalation** (fraud, vip, frustration, identity failure) — short-circuits everything
2. **Identity step-up** — sensitive action without verified identity → ESCALATE
3. **Action-specific rules:** check_payment, check_deferral, check_sim
4. **Default:** AUTHORIZED if no rule objects

**Policy rules:**
- `rules/mandatory_escalation.py`: ESC_FRAUD, ESC_VIP, ESC_FRUSTRATION, ESC_IDENTITY_FAILURE
- `rules/payment.py`: PAY_ABOVE_CAP (>200 TND), PAY_NO_CONFIRMATION
- `rules/deferral.py`: DEF_MIN_AGE (<180 days), DEF_MAX_PER_YEAR (>2), DEF_UNPAID (>150 TND), DEF_NO_ELIGIBLE
- `rules/sim.py`: SIM specific checks
- `rules/outbound.py`: Response guardrails

### 12.3 Policy Service (services/policy-service/src/policy_service/service.py)

Wraps the pure engine with persistence:
1. Compute verdict
2. INSERT into `policy.policy_verdicts` (Postgres) — **every verdict recorded**
3. Append hash-chained audit entry
4. Return `(verdict_result, verdict_id)`
5. `verdict_id` is threaded to execution-service — no action without a verdict

### 12.4 Execution Service (services/execution-service/src/execution_service/service.py)

Idempotent action ledger:
1. Check idempotency key — if seen, return original reference with `replay=True`
2. INSERT pending `action_ledger` row (UNIQUE key enforces at-most-once)
3. Dispatch to target domain adapter
4. Mark succeeded + audit entry
5. Project domain effect (payment/plan/recharge/SIM) in a SAVEPOINT
6. Return `ExecuteResponse(status="executed", reference=..., replay=False)`

---

## 13. Microservices

### 13.1 Context Service (:8101)

**Endpoints:**
- `GET /health` — Liveness
- `GET /internal/context/resolve?msisdn=` — Resolve MSISDN to canonical UUIDs (the only place this happens)
- `GET /context/{msisdn}` — Customer-360 snapshot (404 if unknown)
- `POST /verify-identity` — Check step-up identity answer (last 4 digits of CIN)
- `GET /billing/{customer_id}/invoices` — Read invoices
- `GET /balance/{customer_id}` — Prepaid balance (404 if none)

**Database:** PostgreSQL via `CrmRepository` (crm.customers, crm.subscriptions, billing.invoices, ocs.balance_accounts)

### 13.2 Knowledge Service (:8102)

**Endpoints:**
- `GET /health`
- `POST /search` — RAG search over corpus (returns ranked, source-attributed passages)

**Retrievers:**
- **LexicalRetriever** (default) — Deterministic, score by query-term overlap, no external deps
- **QdrantRetriever** (production) — Embedding search over Qdrant vector store (optional [qdrant] extra)

### 13.3 Decision Service (:8103)

**Endpoints:**
- `GET /health`
- `POST /recommend` — Recommend action + confidence + rationale

```python
def recommend(action_type, context) -> Decision:
    # Score the candidate action based on context
    return Decision(action=action_type, confidence=score, rationale=...)
```

### 13.4 Policy Service (:8104)

**Endpoints:**
- `GET /health`
- `POST /evaluate-action` — Return AUTHORIZED/REFUSED/ESCALATE + rule_id + justification + verdict_id (persisted + audited)
- `POST /evaluate-response` — Guardrail outbound response
- `GET /audit/verify` — Audit-chain integrity check over persisted ledger

### 13.5 Execution Service (:8105)

**Endpoints:**
- `GET /health`
- `POST /execute` — Idempotent action dispatch (needs idempotency_key + policy_verdict_id)
- `GET /audit/verify` — Audit-chain integrity check

### 13.6 Notification Service (:8106)

**Endpoints:**
- `GET /health`
- `POST /notify` — Send one localized written confirmation
- `GET /sent` — List confirmations sent so far

**Channels:** SMS (Twilio REST), WhatsApp (Twilio REST), Email (SMTP). All fall back to mock when credentials missing or `CONNECTOR_MODE=mock`.

**Templates (fr/ar/en):** `ticket_created`, `callback_scheduled`

---

## 14. MCP Servers

### 14.1 ai-knowledge-rag (:8201)

**Tool:** `knowledge_search(query: str) → list[passage]` — RAG/FAQ knowledge search. Read-only, low-risk.

**Transport:** Streamable HTTP at `/mcp`

### 14.2 ticketing-glpi (:8202)

**Tools:** `create_ticket`, `get_ticket_status`, `resolve_ticket`, `lookup_tickets`

- `create_ticket` automatically sends a written confirmation via notification-service
- Uses `MockGlpiClient` by default (in-memory); real GLPI REST adapter replaces it later
- Transport: Streamable HTTP at `/mcp`

### 14.3 messaging-gateway (:8203)

**Tools:** `send_sms`, `send_whatsapp` — Outbound messaging via notification-service.

**NOTE:** Currently a placeholder — actual sending is owned by notification-service (:8106), not MCP.

---

## 15. Frontend Applications

### 15.1 Client Widget (apps/client-widget)

- React 19 + Vite + TypeScript
- Port :5173 (dev)
- Purpose: Browser-based caller widget for testing voice calls
- Gets LiveKit token from token-service (:8107)

### 15.2 Supervisor Dashboard (apps/supervisor-dashboard)

- React 19 + Vite + TypeScript
- Port :5174 (dev)
- Purpose: Back-office dashboard for supervisors
- Reads from business-api (:8108)

---

## 16. Telephony & SIP Transfer

### tools/telephony/sip_transfer.py

```python
async def transfer_to_human(context) -> dict:
    # 1. Resolve available advisor dynamically (routing_client)
    destination = await get_routing_client().resolve_available_advisor(skill_tag)
    if destination is None:
        return await _offer_callback(context)  # Fallback to CallbackScheduleTask
    # 2. SIP cold transfer (ends the current session)
    await job.api.sip.transfer_sip_participant(...)
    return {"outcome": "transferred", "destination": destination.sip_uri}
```

**Fallback chain:** SIP transfer → Callback scheduling (with written confirmation via notification-service)

---

## 17. Observability

### 17.1 OpenTelemetry

- **Package:** `observability-kit` (opentelemetry-sdk + OTLP exporter)
- **Configuration:** `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`, `OTEL_SERVICE_NAME=telecom-agent`
- **Collector:** `otel/opentelemetry-collector-contrib:0.116.1` (receives OTLP, exposes Prometheus endpoint on :8889)
- **Prometheus:** Scrapes collector at `otel-collector:8889`

### 17.2 TTFA/TTFT Metrics (apps/agent-worker/src/observability/metrics_hook.py)

```python
def attach_metrics(session):
    # UsageCollector — aggregates per-component metrics
    # metrics_collected → log + export TTFT (time-to-first-token)
    # agent_state_changed → compute + export TTFA (time-to-first-audio)
    return log_usage  # shutdown callback logs usage summary
```

### 17.3 PII Log Masking (apps/agent-worker/src/observability/log_masking.py)

Installs a logging filter that scrubs phone numbers, emails, and identifier runs from every emitted log record. Uses `PiiMasker` from the `pii-shield` package.

---

## 18. Session State & Tools

### 18.1 SessionUserData (apps/agent-worker/src/session/session_state.py)

```python
@dataclass
class SessionUserData:
    session_id: str
    language: str = "fr"
    customer_context: CustomerContext | None = None
    identity_verified: bool = False
    identity_attempts: int = 0
    recording_consent: bool | None = None
    sentiment_history: list[float] = field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    clarification_attempts: int = 0
    current_persona_skill_tag: str = "general"
    callback_requested: bool = False
    callback_when: str | None = None
    conversation_writer: object | None = None
    session_db_id: str | None = None
    _idempotency_keys: dict[str, str] = field(default_factory=dict)
    
    def new_idempotency_key(self, action_type: str) -> str:
        # One key per (session, action_type) — reused across retries
```

### 18.2 Standard Outcome Contract (tools/outcomes.py)

Every sensitive tool returns one of these shapes:
```python
def refused(rule_id, reason) -> dict  # "This request cannot be completed because: ..."
def escalate(rule_id, reason) -> dict  # "This needs a human specialist (...)"
def executed(action_type, reference, replay=False) -> dict  # "The ... was completed. Ref: ..."
def failed(reason) -> dict  # "The action could not be completed right now."
```

### 18.3 Tools Overview

| Tool | Module | Type | Purpose |
|------|--------|------|---------|
| `request_clarification` | clarification_tools.py | LLM tool | Ask a clarifying question (counts attempts → 2 → escalate) |
| `route_to_billing` | routing_tools.py | LLM tool | Hand off to BillingAgent |
| `route_to_technical` | routing_tools.py | LLM tool | Hand off to TechnicalAgent |
| `escalate_to_manager` | escalation_tools.py | LLM tool | Hand off to ManagerAgent (records escalation case) |
| `get_invoice_summary` | billing_tools.py | LLM tool | Read latest invoice (read-only) |
| `get_balance_summary` | billing_tools.py | LLM tool | Read prepaid balance (read-only) |
| `get_plan_details` | account_tools.py | LLM tool | Read current plan (read-only) |
| `change_plan` | account_tools.py | LLM tool | Change plan (guarded) |
| `top_up` | account_tools.py | LLM tool | Top up prepaid balance (guarded) |
| `toggle_roaming` | account_tools.py | LLM tool | Enable/disable roaming (guarded) |
| `make_payment` | billing_agent.py | Inline | Take a payment (amount confirm → guarded) |
| `request_payment_deferral` | billing_agent.py | Inline | Request deferral (guarded) |
| `unblock_sim` | technical_agent.py | Inline | Unblock SIM (identity-gated + guarded) |
| `transfer_to_human` | sip_transfer.py | LLM tool | SIP transfer or callback |
| `knowledge_search` | MCP toolset | MCP | Search knowledge base |
| `create_ticket` | MCP toolset | MCP | Create GLPI ticket + send confirmation |
| `get_ticket_status` | MCP toolset | MCP | Check ticket status |
| `resolve_ticket` | MCP toolset | MCP | Resolve ticket |
| `lookup_tickets` | MCP toolset | MCP | Look up tickets |

---

## 19. Database Schema & Persistence

### 19.1 Persistence Package (packages/persistence/)

**Engine:** SQLAlchemy 2.0 sync engine/session from `DATABASE_URL`.
**UUID PK model:** All tables use UUID primary keys with `created_at` / `updated_at` timestamps.
**Schema-per-bounded-context:** 12 PostgreSQL schemas.

### 19.2 Schemas and Tables (27 tables)

| Schema | Tables | Purpose |
|--------|--------|---------|
| `crm` | customers, subscriptions, consent_records, customer_interactions | Customer data, identity, consent |
| `billing` | accounts, invoices, invoice_items, notifications | Billing, invoices, notifications |
| `ocs` | balance_accounts | Prepaid balances |
| `execution` | action_ledger | Idempotent action dispatch log |
| `policy` | policy_verdicts | Every policy verdict (regardless of outcome) |
| `conversation` | call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules | Durable conversation record |
| `audit` | audit_ledger | Hash-chained append-only audit trail |
| `ticketing` | tickets, ticket_messages | Ticket mirror |
| `provisioning` | (phase 2) | Provisioning data |
| `oss` | (phase 2) | OSS data |
| `network` | (phase 2) | Network data |
| `kpi` | (phase 2) | KPI data |

**Views:** `crm.v_subscription_live` — read-through view for live subscriptions.

### 19.3 Alembic Migrations

- Migration `0001`: Extensions + 12 schemas + set_updated_at trigger + crm/billing/ocs tables + view
- Migrations `0002`–`0006`: Policy verdicts, action ledger, conversation tables, ticketing mirror, notifications, project domain effects

### 19.4 Seed Data

- **seed_pilot.py**: 3 canonical callers with real TND amounts:
  - `+21620155320` — Amine (fr, regular)
  - `+21629744108` — Yousra (ar, VIP)
  - `+21652310977` — Karim (en, regular, 73.900 TND overdue)
- **seed_reference.py**: Reference catalogs

---

## 20. Security

### 20.1 Service-to-Service Auth

- **Package:** `service-auth` (X-API-Key)
- **Implementation:** FastAPI dependency `require_internal_key` on internal services + `internal_headers()` on worker clients
- **Opt-in:** When `INTERNAL_API_KEY` is unset (dev/CI), auth is a no-op
- **Applied to:** All 6 domain services (context, knowledge, decision, policy, execution, notification)
- **NOT applied:** `/health` endpoints (always open), token-service, business-api

### 20.2 CORS

- **token-service:** `CORS_ORIGINS` (default: `http://localhost:5173,http://localhost:5174`)
- **business-api:** `CORS_ORIGINS` (default: `http://localhost:5174`)

### 20.3 PII Protection

- `pii-shield` package — masks phone numbers, emails, national IDs
- Logging filter in worker — scrubs PII from every log record
- Conversation transcripts — PII-masked before they leave the worker
- Audit trail contains references, never PII

### 20.4 Defense in Depth

1. Identity verification — step-up (last 4 digits of CIN) via context-service
2. Decision service — confidence threshold
3. Policy service — deterministic rules, fail-closed (ESCALATE on service error)
4. Execution — idempotent, no action without a persisted verdict_id
5. Audit — hash-chained, verifiable

### 20.5 RBAC (business-api)

Three roles per spec section 17:
- `conseiller` — Customer-360, session detail
- `superviseur` — Escalation queue, verdicts, actions, KPIs
- `administrateur` — Audit verify, business rules, integrity job, retention job

---

## 21. Deployment

### 21.1 Quick Start (Development)

```bash
cp .env.example .env          # Fill in the ⚠ values (LiveKit + provider keys)
make dev                      # = install → infra → migrate → seed → honcho start
make frontends                # First time only: npm install web apps
make health                   # Probe all services
```

### 21.2 Container Path (Docker Compose)

```bash
make up                       # Build + start all containers
make down                     # Stop everything
make rebuild                  # Stop → rebuild → restart
```

### 21.3 Kubernetes (Helm)

Two chart options:
- `infra/helm/telecom-platform/` — Full chart with 6 templates: services, worker, infra, gateway, OTel, secrets
- `deploy/helm/telecom-agent/` — Simpler chart with templated Deployment/Service for 8 deployables

---

## 22. Documentation Index

| File | Description |
|------|-------------|
| `docs/RUN.md` | How to run the platform (2 paths: honcho vs containers) |
| `docs/AI_MODEL_INVENTORY.md` | Complete model inventory (280 lines) |
| `docs/architecture/phase-0-verification-gate/00-DECISION-RECORD.md` | DR-0 — Provider/turn-detector decision record |
| `docs/phase-7/README.md` | Phase 7 — Execution & Sensitive Actions |
| `docs/phase-8/README.md` | Phase 8 — Sentiment & Escalation |
| `docs/phase-9/README.md` | Phase 9 — Ticketing & Notifications |
| `docs/persistence/README.md` | P1 — CRM/Billing/OCS read foundation |
| `docs/persistence/PERSISTENCE-P2-README.md` | P2 — Safety Core on Postgres |
| `docs/persistence/PERSISTENCE-P3-README.md` | P3 — Conversation record |
| `docs/persistence/PERSISTENCE-P4-README.md` | P4 — Execution write projections |
| `docs/persistence/PERSISTENCE-P5-README.md` | P5 — Ticketing mirror + Notification log |
| `docs/persistence/PERSISTENCE-P6-README.md` | P6 — Reference catalogs + business-api + integrity job |
| `docs/persistence/ADR-0001-data-layer.md` | ADR — Data layer architecture decision |
| `docs/patches/DIAGNOSTIC-RESOLUTION.md` | All 11 diagnostic items resolved |
| `docs/patches/PATCHSET-1-SECURITY-HYGIENE.md` | Security hardening + code hygiene |
| `docs/patches/PATCHSET-2-PERSISTENCE.md` | Persistence completeness |
| `docs/patches/PATCHSET-3-INTEGRATIONS.md` | Real integrations behind CONNECTOR_MODE |
| `docs/patches/PATCHSET-4-INFRA-OPS.md` | Infra, storage & ops |
| `docs/patches/TESTER-REPORT-RESOLUTION.md` | Tester report items resolved |
| `docs/compliance/PILOT-READINESS.md` | 18 built + 7 staging-gated items |
| `docs/compliance/TRACEABILITY.md` | CDC-to-component traceability matrix |
| `docs/compliance/UAT-PLAN.md` | 14 FR/AR/EN voice scenarios |

---

## 23. Known Issues & Open Items

### 23.1 Current Issues (from diagnostics/runtime)

| Issue | Impact | Workaround |
|-------|--------|------------|
| Gemini model ID `gemini-2.5-flash-latest` may 404 | LLM primary fails | Update to a valid model ID |
| MCP `streamablehttp_client()` TypeError | MCP tools fail in containers | `mcp` library version mismatch |
| OTel collector unreachable (`StatusCode.UNAVAILABLE`) | No telemetry export | OTel no-ops silently |
| LLM inference timeout too short (5s < 10s minimum) | Gemini may time out | Increase `attempt_timeout` or per-provider timeout |
| Turn-detection model file path mismatch | Turn detection may fail | Silero VAD model path issue |

### 23.2 Pilot Readiness — Staging-Gated Items (7)

- [ ] Full spoken UAT in FR/AR/EN for every CDC §5 scenario
- [ ] Resilience chaos test: STT/LLM/TTS primary-failure fallback per language
- [ ] Load test green against sub-second TTFA budget
- [ ] Soak test: no resource/state bleed across long sequential runs
- [ ] Least-privilege DB roles granted; append-only enforced
- [ ] Live connector bindings confirmed (OCS/Billing/Payment/SMS/GLPI)
- [ ] Retention window + export/delete workflow validated

### 23.3 Provider Key Status

| Provider | Role | Status |
|----------|------|--------|
| Deepgram | STT primary | **Live key present** |
| Gladia | STT fallback | Key present |
| Azure | STT/TTS fallback | EMPTY — add to activate |
| Google Gemini | LLM primary | **Live key present** |
| NVIDIA NIM | LLM fallback | Key present |
| OpenAI | LLM fallback | EMPTY / disabled |
| Groq | LLM fallback | Key present |
| ElevenLabs | TTS primary | EMPTY — add to activate |
| Cartesia | TTS fallback | Key present |
| Twilio | SMS/WhatsApp | EMPTY — add to activate |
| SendGrid/SMTP | Email | EMPTY — add to activate |

---

*End of system_complete.md — generated from the live codebase on version_07 branch, commit 0e50dcb.*
