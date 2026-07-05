# Telecom AI Agent Platform — Complete Project Reference Report

> **Generated:** 2026-07-04  
> **Purpose:** Comprehensive reference for backend engineers, QA testers, and stakeholders to validate all code, business logic, architecture, and infrastructure.  
> **Technology Stack:** Python 3.12, FastAPI, LiveKit Agents, PostgreSQL, Redis, Qdrant, MinIO, React/TypeScript.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Design Principles](#2-architecture--design-principles)
3. [Directory Structure (Complete Tree)](#3-directory-structure-complete-tree)
4. [Root Configuration Files](#4-root-configuration-files)
5. [Apps — Detailed Breakdown](#5-apps--detailed-breakdown)
   - 5.1 [agent-worker (Voice AI Orchestrator)](#51-agent-worker)
   - 5.2 [business-api (Back-Office REST API)](#52-business-api)
   - 5.3 [token-service (LiveKit Token Minting)](#53-token-service)
   - 5.4 [client-widget (React Voice Widget)](#54-client-widget)
   - 5.5 [supervisor-dashboard (React Admin Dashboard)](#55-supervisor-dashboard)
6. [Services — Detailed Breakdown](#6-services--detailed-breakdown)
   - 6.1 [context-service (Customer-360 / CRM)](#61-context-service)
   - 6.2 [knowledge-service (RAG / FAQ)](#62-knowledge-service)
   - 6.3 [decision-service (Candidate-Action Ranking)](#63-decision-service)
   - 6.4 [policy-service (Deterministic Verdict Engine)](#64-policy-service)
   - 6.5 [execution-service (Idempotent Action Dispatch)](#65-execution-service)
   - 6.6 [notification-service (Written Confirmations)](#66-notification-service)
7. [MCP Servers — Detailed Breakdown](#7-mcp-servers--detailed-breakdown)
   - 7.1 [ai-knowledge-rag (Knowledge Search)](#71-ai-knowledge-rag)
   - 7.2 [messaging-gateway (SMS/WhatsApp)](#72-messaging-gateway)
   - 7.3 [ticketing-glpi (GLPI Ticket Lifecycle)](#73-ticketing-glpi)
8. [Packages — Detailed Breakdown](#8-packages--detailed-breakdown)
9. [Infrastructure & Deployment](#9-infrastructure--deployment)
10. [Scripts & Automation](#10-scripts--automation)
11. [Database Schema (Alembic Migrations)](#11-database-schema-alembic-migrations)
12. [Testing Strategy](#12-testing-strategy)
13. [CI/CD Pipeline](#13-cicd-pipeline)
14. [Business Logic & Data Flow](#14-business-logic--data-flow)
15. [Security Model](#15-security-model)
16. [Fixes Directory (Hot-Patch Overlay)](#16-fixes-directory-hot-patch-overlay)
17. [Documentation Inventory](#17-documentation-inventory)

---

## 1. Project Overview

**Telecom AI Voice Agent Platform** is a self-hosted, open-source LiveKit-based platform that:
- Handles frequent telecom customer requests over real-time **voice** (primary) and **text**
- Supports **French (primary), Arabic, and English** with per-language STT/TTS chains
- Applies **deterministic business rules** before any sensitive action
- Executes real actions (payment, SIM unblock, ticket creation)
- Escalates to a human with a full dossier when needed
- AI inference (STT/LLM/TTS) is cloud-based; everything touching PII, audit, and business systems is self-hosted

### Key Metrics
- **~200 source files** across Python and TypeScript
- **5 apps**, **6 domain services**, **3 MCP servers**, **10 shared packages**
- **8 Alembic database migrations** covering 12 schemas
- **PostgreSQL** as primary data store, Redis for caching, Qdrant for vectors, MinIO for object storage
- **Docker Compose** for local dev + **Helm charts** for Kubernetes deployment
- **GitHub Actions CI** with lint, test, migration, Docker build, and security scanning

### Business Use Case (Tunisie Telecom)
The platform is built for Tunisie Telecom, a Tunisian telecom operator. It handles:
- **Billing**: invoice consultation, payment processing, payment deferrals
- **Account Services**: plan changes, prepaid top-ups, roaming activation
- **Technical Support**: SIM unblock/reactivate, network troubleshooting
- **Knowledge Base**: FAQ, procedure lookups, offer consultation
- **Escalation**: human hand-off with full call dossier + ticket creation

---

## 2. Architecture & Design Principles

### Non-Negotiable Rules (from `README.md`)
1. **Clean/Hexagonal + DDD + SOLID**: Business rules never import LiveKit/vendor SDKs — they sit behind ports in `packages/domain-core`
2. **Composition Root**: `apps/agent-worker/src/server.py` wires everything; zero business logic
3. **Thin Tools**: Tools are thin facades calling domain services via typed clients
4. **Deterministic Policy**: Returns `AUTHORIZED / REFUSED / ESCALATE` + rule-id + justification before every action, never bypassable, written to hash-chained audit ledger
5. **No Sensitive-Action Skips Decision -> Policy -> Execution**: Sensitive actions are idempotent
6. **Direct LiveKit Provider Plugins + FallbackAdapter**: Never LiveKit Inference
7. **FR/AR/EN Only**: Per-language routing with verified provider support

### Data Flow (Sensitive Action Path)
```
Caller Intent → Triage Agent → Tool Call (e.g. make_payment)
  → Decision Service (rank action, confidence)
    → Policy Service (deterministic verdict: AUTHORIZED/REFUSED/ESCALATE)
      → Execution Service (idempotent dispatch + audit chain)
        → Domain Projection (payment, sim_case, etc.)
```

### Provider Redundancy (Failure Chains)
- **STT**: Deepgram Nova-3 (primary) → Azure STT (fallback)
- **TTS**: ElevenLabs Flash v2.5 (primary) → Azure Neural TTS (fallback)
- **LLM**: Gemini 2.5 Flash (primary) → NVIDIA NIM → OpenAI GPT-4o-mini → Groq
- **Turn Detection**: Audio-native EOU model (local CPU) → Silero VAD

---

## 3. Directory Structure (Complete Tree)

```
telecom-ai-agent-platform/
│
├── .agents/                                    # OpenCode agent definitions (empty)
├── .github/workflows/
│   └── ci.yml                                  # GitHub Actions CI pipeline
├── .kombai/                                    # Kombai design tool cache
├── .venv/                                      # Python virtual environment
│
├── apps/                                       # Independently deployable apps
│   ├── agent-worker/                           # LiveKit voice AI orchestrator
│   │   ├── Dockerfile
│   │   ├── livekit.toml
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── server.py                       # Composition root
│   │   │   ├── agents/                         # AI personas (5 agents)
│   │   │   ├── clients/                        # Typed HTTP clients to services
│   │   │   ├── config/                         # Settings + language presets
│   │   │   ├── conversation/                   # Durable conversation writer
│   │   │   ├── entrypoints/                    # Worker entrypoint
│   │   │   ├── mcp_clients/                    # MCP tool integrations
│   │   │   ├── observability/                  # PII masking + metrics
│   │   │   ├── providers/                      # STT/TTS/LLM/VAD + resilience
│   │   │   ├── sentiment/                      # Per-turn sentiment scoring
│   │   │   ├── session/                        # Session state + customer context
│   │   │   ├── tasks/                          # Interactive tasks (consent, payment, etc.)
│   │   │   ├── telephony/                      # SIP transfer
│   │   │   └── tools/                          # Agent-callable tools
│   │   └── tests/
│   │
│   ├── business-api/                           # Back-office REST API
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/business_api/
│   │   │   ├── main.py                         # FastAPI app + RBAC endpoints
│   │   │   ├── kpis.py                         # KPI math
│   │   │   ├── repositories.py                 # Read-side DB queries
│   │   │   ├── security.py                     # RBAC role enforcement
│   │   │   ├── api/                            # (empty)
│   │   │   ├── application/                    # (empty)
│   │   │   ├── infrastructure/                 # (empty)
│   │   │   └── jobs/                           # Integrity + retention jobs
│   │   └── tests/
│   │
│   ├── client-widget/                          # React voice widget
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   └── src/
│   │
│   ├── supervisor-dashboard/                   # React admin dashboard
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   └── src/
│   │       ├── api.ts                          # API client
│   │       ├── types.ts                        # TypeScript types
│   │       └── components/
│   │           ├── EscalationQueue.tsx
│   │           ├── KpiPanel.tsx
│   │           └── SessionInspector.tsx
│   │
│   └── token-service/                          # LiveKit JWT minting
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/token_service/main.py
│       └── tests/
│
├── services/                                   # Domain microservices
│   ├── context-service/                        # Customer-360, identity, CRM reads
│   │   ├── Dockerfile, pyproject.toml
│   │   ├── src/context_service/
│   │   │   ├── main.py                         # FastAPI app port 8101
│   │   │   ├── mapping.py                      # Pure mapping helpers
│   │   │   ├── repositories.py                 # CrmRepository (Postgres)
│   │   │   └── schemas.py                      # Pydantic DTOs
│   │   └── tests/
│   │
│   ├── decision-service/                       # Candidate-action ranking
│   │   ├── Dockerfile, pyproject.toml
│   │   ├── src/decision_service/
│   │   │   ├── main.py                         # FastAPI app port 8103
│   │   │   ├── schemas.py
│   │   │   └── scorer.py                       # Deterministic scorer
│   │   └── tests/
│   │
│   ├── execution-service/                      # Idempotent action dispatch
│   │   ├── Dockerfile, pyproject.toml
│   │   ├── src/execution_service/
│   │   │   ├── main.py                         # FastAPI app port 8105
│   │   │   ├── executor.py                     # Mock/live dispatch
│   │   │   ├── projections.py                  # Domain effect projections
│   │   │   ├── schemas.py
│   │   │   └── service.py                      # ExecutionService
│   │   └── tests/
│   │
│   ├── knowledge-service/                      # RAG over documentation corpus
│   │   ├── Dockerfile, pyproject.toml
│   │   ├── src/knowledge_service/
│   │   │   ├── main.py                         # FastAPI app port 8102
│   │   │   ├── corpus.py                       # English knowledge corpus
│   │   │   ├── retriever.py                    # Lexical + Qdrant retriever
│   │   │   └── schemas.py
│   │   └── tests/
│   │
│   ├── notification-service/                   # Written confirmations
│   │   ├── Dockerfile, pyproject.toml
│   │   ├── src/notification_service/
│   │   │   ├── main.py                         # FastAPI app port 8106
│   │   │   ├── channels.py                     # Channel strategies
│   │   │   ├── schemas.py
│   │   │   ├── service.py                      # NotificationService
│   │   │   └── templates.py                    # Localized templates
│   │   └── tests/
│   │
│   └── policy-service/                         # Deterministic verdict engine
│       ├── Dockerfile, pyproject.toml
│       ├── src/policy_service/
│       │   ├── main.py                         # FastAPI app port 8104
│       │   ├── config.py                       # Threshold configuration
│       │   ├── engine.py                       # Rule engine
│       │   ├── schemas.py
│       │   ├── service.py                      # PolicyService
│       │   └── rules/                          # Individual policy rules
│       │       ├── base.py
│       │       ├── deferral.py
│       │       ├── mandatory_escalation.py
│       │       ├── outbound.py
│       │       ├── payment.py
│       │       └── sim.py
│       └── tests/
│
├── mcp-servers/                                # MCP (Model Context Protocol) servers
│   ├── ai-knowledge-rag/                       # Knowledge search MCP
│   ├── messaging-gateway/                      # SMS/WhatsApp MCP
│   └── ticketing-glpi/                         # GLPI ticket lifecycle MCP
│
├── packages/                                   # Shared libraries
│   ├── audit-trail/                            # Hash-chained audit ledger
│   ├── cache/                                  # Redis/null cache abstraction
│   ├── domain-core/                            # Pure domain entities, ports, value objects
│   ├── integration-adapters/                   # Per-legacy-system adapters
│   ├── notification-client/                    # Channel-strategy notifier
│   ├── object-storage/                         # MinIO/S3 null-safe wrapper
│   ├── observability-kit/                      # OpenTelemetry setup + metrics
│   ├── persistence/                            # SQLAlchemy models, engine, migrations
│   ├── pii-shield/                             # PII masking
│   └── service-auth/                           # Internal API key auth
│
├── infra/                                      # Infrastructure definitions
│   ├── ci-cd/                                  # CI/CD documentation
│   ├── docker-compose/                         # Docker Compose files + nginx
│   ├── helm/                                   # Kubernetes Helm chart
│   └── livekit-server/                         # LiveKit self-hosted docs
│
├── deploy/                                     # Deployment configs
│   ├── backup/                                 # Backup/restore scripts
│   ├── gateway/                                # API gateway (nginx)
│   ├── helm/                                   # Telecom agent Helm chart
│   ├── otel/                                   # OpenTelemetry collector
│   ├── postgres/                               # Postgres Docker Compose
│   └── secrets/                                # Secrets management
│
├── scripts/                                    # Utility scripts
│   ├── health_check.py
│   ├── run_tests.py
│   ├── install_dev.ps1
│   ├── start_dev.ps1
│   ├── start_dev_containers.ps1
│   ├── stop_dev.ps1
│   └── fix_frontend_deps.sh
│
├── docs/                                       # Documentation
│   ├── architecture/                           # Phase-0 decision record + provider matrix
│   ├── compliance/                             # Pilot readiness, traceability, UAT plan
│   ├── patches/                                # Patch sets (security, persistence, infra)
│   ├── persistence/                            # P1-P6 persistence ADRs + documentation
│   ├── phases/                                 # Phase 11-12 READMEs
│   └── phase-7/, phase-8/, phase-9/, phase-10/ # Phase-specific docs
│
├── fixes/                                      # Hot-patch overlay (parallel fix-tree)
│
├── tests/                                      # System-level tests
│   └── load/                                   # Load + soak testing
│       ├── loadtest.py
│       ├── soak.py
│       └── README.md
│
├── .env.example                                # Environment template (single source of truth)
├── .gitignore
├── .dockerignore
├── Makefile                                    # Unified dev commands
├── Procfile                                    # Honcho process definitions
├── pyproject.toml                              # Root tooling config (ruff, mypy)
├── start.ps1                                   # PowerShell startup script
├── start_commands.md                           # Startup guides
├── system.md                                   # System-level prompts
├── prompt.md                                   # Agent prompts
├── test_session.py                             # Session building test
├── ALL_SYSTEM_ARCHITECTURE.md                  # Full architecture doc
├── CODE_DIAGNOSTIC.md                          # Code diagnostic findings
├── DIAGNOSTIC-RESOLUTION.md                    # Diagnostic resolution
├── ERROR_INVESTIGATION.md                      # Error investigation
├── SESSION_LOG_ANALYSIS.md                     # Session log analysis
├── STARTUP_DIAGNOSTIC.md                       # Startup diagnostic
└── SYSTEM_CODES.md                             # System error codes
```

---

## 4. Root Configuration Files

### `pyproject.toml` (Root)
```toml
# Root tooling config only (no build target here). Per-package builds live in each package's pyproject.
[tool.ruff]
target-version = "py312"
line-length = 110
extend-exclude = ["**/alembic/versions/*", "**/node_modules/**", "**/dist/**", "fixes/**"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = [
  "persistence", "audit_trail", "domain_core", "pii_shield", "observability_kit",
  "service_auth", "notification_client",
]

[tool.mypy]
python_version = "3.12"
warn_unused_ignores = true
warn_redundant_casts = true
ignore_missing_imports = true
disallow_untyped_defs = false
exclude = "(alembic/versions|node_modules|dist|/tests/)"
```

### `Makefile` — One command to install, run, verify
```makefile
# Key targets:
#   make dev        — install + infra + migrate + seed + honcho start (everything)
#   make up         — all containers (docker compose)
#   make down       — stop everything
#   make rebuild    — rebuild + restart containers
#   make install    — install all packages in correct order
#   make frontends  — npm install for both web apps
#   make health     — probe all /health endpoints
#   make test       — run offline test suite
#   make migrate    — alembic upgrade head
#   make seed       — seed pilot data + reference catalogs
#   make infra      — start infrastructure containers (postgres/redis/qdrant/minio/otel)
#   make infra-livekit — also start self-hosted LiveKit
#   make live-logs  — follow token-service + agent-worker logs
```

### `Procfile` — Honcho process definitions
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

### `.env.example` (Key Sections)
- **Database**: PostgreSQL connection, pool settings
- **LiveKit**: URL, API key/secret, agent name
- **STT**: Deepgram API key (primary), Azure Speech (fallback), Gladia (optional)
- **TTS**: ElevenLabs API key (primary), Azure/Cartesia (fallback)
- **LLM Chain**: Google Gemini (primary), OpenAI, NVIDIA NIM, Groq (fallback tiers)
- **Domain Services**: URLs for all 6 services + 3 MCP servers
- **Legacy Adapters**: OCS, Billing, Payment, CRM, NMS, GLPI URLs
- **Infrastructure**: Redis, Qdrant, MinIO, OTEL endpoints
- **Policy Thresholds**: Payment cap, deferral age/count, unpaid thresholds
- **RBAC**: Default admin role for business API

### `start.ps1` — PowerShell startup helper
Commands: `up`, `down`, `rebuild`, `build`, `logs`, `status`, `health`, `help`

---

## 5. Apps — Detailed Breakdown

### 5.1 agent-worker

**Purpose:** LiveKit Agents real-time orchestrator. Composition root only — zero business logic.

**Port:** N/A (registers with LiveKit server)
**Dependencies:** `livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia]==1.6.3`, `mcp`, `pydantic`, `httpx`, `structlog`, all internal packages

#### Architecture (Files grouped by function)

##### `src/server.py` — Composition Root
- Loads env vars via `dotenv`
- Configures PII-masked logging
- Configures OpenTelemetry tracer
- Creates `AgentServer` with optional `agent_name`
- Entrypoint (`@server.rtc_session()`):
  1. Builds agent session via `build_agent_session(settings, language)`
  2. Pre-fetches caller Customer-360 via `get_context_client().get_snapshot(msisdn)`
  3. Opens conversation writer (async, off-voice-path)
  4. Registers shutdown callback (finalize session + sentiment + audit)
  5. Registers speech/tool callbacks for logging
  6. Builds noise cancellation (optional)
  7. Starts session with `TriageAgent(language=language)`

##### `src/agents/` — 5 AI Personas

| Agent | File | Role | Tools |
|---|---|---|---|
| **TriageAgent** | `triage_agent.py` | First contact — consent, greet, route, FAQ | `request_clarification`, `route_to_billing`, `route_to_technical`, `escalate_to_manager`, `knowledge_search` |
| **BillingAgent** | `billing_agent.py` | Bills, invoices, payments, deferrals | `get_invoice_summary`, `get_balance_summary`, `make_payment`, `request_payment_deferral`, `escalate_to_manager`, `knowledge_search` |
| **AccountServicesAgent** | `account_services_agent.py` | Plans, recharges, roaming | `get_plan_details`, `change_plan`, `top_up`, `toggle_roaming`, `escalate_to_manager` |
| **TechnicalAgent** | `technical_agent.py` | SIM, network, connectivity | `unblock_sim`, `escalate_to_manager`, `knowledge_search`, `create_ticket`, `resolve_ticket` |
| **ManagerAgent** | `manager_agent.py` | Human escalation target | `transfer_to_human`, `create_ticket` |

**BaseAgent** (`base_agent.py`) — shared behavior:
- Per-turn sentiment scoring via `sentiment_scorer.py`
- Proactive de-escalation note injection when frustration is high
- Conversation turn logging (off-voice-path via `ConversationWriter`)
- Transcript extraction from ChatMessage objects

##### `src/providers/` — Provider Abstractions

| File | Component | Description |
|---|---|---|
| `stt.py` | Speech-to-Text | Builds `FallbackAdapter` chain: Deepgram Nova-3 → Azure Speech → Gladia (optional) |
| `tts.py` | Text-to-Speech | Builds `FallbackAdapter` chain: ElevenLabs Flash v2.5 → Azure Neural TTS → Cartesia (optional) |
| `llm.py` | Large Language Model | Builds `FallbackAdapter` chain: Gemini 2.5 Flash → NVIDIA NIM → GPT-4o-mini → Groq |
| `vad.py` | Voice Activity Detection | Silero VAD with configurable `min_silence_duration` |
| `turn_detection.py` | Turn Detection | Audio-native EOU model (covers FR/AR/EN) |
| `language_router.py` | Language Routing | Routes between language-specific STT/TTS chains |
| `session_factory.py` | Session Factory | Assembles all providers into a `VoicePipelineAgent` |
| `noise_cancellation.py` | Noise Cancellation | Optional RNNoise-based cancellation |
| `_resilience.py` | Resilience Utilities | Fallback adapter construction, chaos toggle injection |
| `groq_adapter.py` | Groq LLM Adapter | Custom Groq provider adapter |
| `nvidia_adapter.py` | NVIDIA NIM Adapter | Custom NVIDIA NIM provider adapter |

**Chaos Engineering:** `CHAOS_BREAK_STT`, `CHAOS_BREAK_LLM`, `CHAOS_BREAK_TTS` env flags simulate primary provider failure for resilience testing.

##### `src/clients/` — Typed HTTP Clients to Domain Services

| File | Client | Target | Key Methods |
|---|---|---|---|
| `context_client.py` | `ContextClient` | context-service:8101 | `get_snapshot(msisdn)`, `verify_identity()`, `get_invoices()`, `get_balance()` |
| `decision_client.py` | `DecisionClient` | decision-service:8103 | `recommend(action_type, context)` |
| `policy_client.py` | `PolicyClient` | policy-service:8104 | `evaluate_action(context)`, `evaluate_response(text)` — fail-closed to ESCALATE |
| `execution_client.py` | `ExecutionClient` | execution-service:8105 | `execute(idempotency_key, ...)` |
| `notification_client.py` | `NotificationClient` | notification-service:8106 | `notify(customer_id, template, ...)` |
| `routing_client.py` | `RoutingClient` | (None — pilot mock) | `resolve_available_advisor(skill_tag)` — always None (callback fallback) |

All clients use `service_auth.internal_headers()` for inter-service auth and are cached via `lru_cache`.

##### `src/tools/` — Agent-Callable Tools

| File | Tool | Description |
|---|---|---|
| `account_tools.py` | `get_plan_details`, `change_plan`, `top_up`, `toggle_roaming` | Account management |
| `billing_tools.py` | `get_balance_summary`, `get_invoice_summary` | Read billing data |
| `clarification_tools.py` | `request_clarification` | Handle ambiguous requests (tracks clarification count, escalates after 2 failures) |
| `escalation_tools.py` | `escalate_to_manager` | Human hand-off with dossier |
| `routing_tools.py` | `route_to_billing`, `route_to_technical` | Inter-agent routing with `agent.transfer_to_agent()` |
| `technical_tools.py` | (via `@function_tool()` in technical_agent.py) | `unblock_sim` |
| `guarded_action.py` | `execute_guarded_action` | Decision → Policy → Execution pipeline wrapper |
| `guards.py` | `ensure_identity_verified` | Identity verification guard |
| `outcomes.py` | `executed()`, `refused()`, `escalate()`, `failed()` | Standard result helpers |

##### `src/tasks/` — Interactive Tasks (User Confirmation Flows)

| File | Task | Description |
|---|---|---|
| `consent_task.py` | `ConsentTask` | Recording consent via `generate_reply` + await |
| `identity_verification_task.py` | `IdentityVerificationTask` | Step-up identity via last 4 digits of national ID |
| `payment_confirm_task.py` | `PaymentConfirmTask` | Confirm payment amount before proceeding |
| `callback_schedule_task.py` | `CallbackScheduleTask` | Schedule callback (24h placeholder) |
| `sim_replacement_task_group.py` | `SimReplacementTaskGroup` | Multi-step SIM replacement flow |

##### `src/session/` — Session State Management

| File | Class | Purpose |
|---|---|---|
| `session_state.py` | `SessionState` | In-process per-call state (counters, flags) |
| `customer_context.py` | `CustomerContext` | Customer-360 snapshot with `from_snapshot()` factory |
| `user_data.py` | `SessionUserData` | Full user data bundle carried on session |

##### `src/conversation/writer.py` — `ConversationWriter`
- **Non-blocking**: enqueue-and-forget pattern
- Background task drains queue and writes to Postgres via sync SQLAlchemy `to_thread()`
- PII-masks transcripts before they leave the worker
- Writes: `CallSession`, `Turn`, `SentimentSample`, `EscalationCase`, `CallbackSchedule`, `ConsentRecord`
- Fault-tolerant: writes are logged and dropped on DB failure

##### `src/sentiment/sentiment_scorer.py`
- Per-turn sentiment analysis using a single logistic-regression classifier
- Tracks frustration history via `SessionUserData.sentiment_history`
- Heuristic: repeated negative turns → `should_offer_escalation = True`

##### `src/mcp_clients/` — MCP Tool Integrations

| File | Toolset | MCP Server URL |
|---|---|---|
| `knowledge_toolset.py` | `build_knowledge_toolset()` → `knowledge_search` | knowledge-service:8102 |
| `ticketing_toolset.py` | `build_ticketing_toolset()` → `create_ticket`, `get_ticket_status`, `resolve_ticket`, `lookup_tickets` | ticketing-glpi:8202 |

##### `src/observability/`
- `log_masking.py` — `install_pii_masking()`: filters PII from log output
- `metrics_hook.py` — `attach_metrics()`: attaches OTel metric callbacks to session events
- `metrics_hooks.py` — Additional metrics hooks

##### `src/telephony/sip_transfer.py`
- `transfer_to_human()` tool: resolves advisor via `RoutingClient`, performs SIP refer transfer, or schedules callback
- Dynamic destination resolved by skill tag (never hardcoded)

##### `src/config/`
- `settings.py` — `Settings(BaseSettings)`: Twelve-Factor, Pydantic-based env loading
- `language_presets.py`: Per-language STT/TTS config (Deepgram language codes, Azure locales, ElevenLabs ISO, Cartesia voice UUIDs)
- Greeting templates for FR/AR/EN

---

### 5.2 business-api

**Purpose:** Back-office REST API for supervisor/admin dashboards. Read-or-audited endpoints.

**Port:** 8108
**Key Dependencies:** `fastapi`, `sqlalchemy`, `object-storage`, `audit-trail`, `persistence`

#### API Endpoints

| Method | Path | Role Required | Description |
|---|---|---|---|
| GET | `/health` | None | Liveness probe |
| GET | `/api/v1/customers/{id}/360` | conseiller | Full Customer-360 (profile, subs, invoices, tickets) |
| GET | `/api/v1/sessions/{id}` | conseiller | Masked transcript + sentiment timeline + disposition |
| GET | `/api/v1/escalations` | superviseur | Escalation queue with dossiers (filterable by status) |
| GET | `/api/v1/policy/verdicts` | superviseur | All policy verdicts for a session |
| GET | `/api/v1/actions` | superviseur | Failed/retrying actions from action ledger |
| GET | `/api/v1/kpis` | superviseur | Containment/escalation KPIs |
| GET | `/api/v1/audit/verify` | administrateur | Hash-chain integrity check |
| GET | `/api/v1/reference/business-rules` | administrateur | Versioned Policy rule registry |
| GET | `/api/v1/jobs/integrity` | administrateur | Cross-domain integrity + audit-chain verification |
| POST | `/api/v1/jobs/retention` | administrateur | Audited retention/purge job (dry_run=True by default) |

#### RBAC Hierarchy
- `conseiller` (rank 1) — read customer data
- `superviseur` (rank 2) — operational supervision
- `administrateur` (rank 3) — system administration

Role is read from `X-Role` header (or `BUSINESS_API_DEFAULT_ROLE` env var for dev).

#### Jobs
- `jobs/integrity.py` — `run_integrity()`: cross-domain referential integrity + audit-chain verify
- `jobs/retention.py` — `run_retention()`: audited data retention/purge (default 90 days)

#### KPI Definitions (`kpis.py`)
- `total_sessions`, `resolved`, `escalated`, `containment_rate`, `escalation_rate`, `avg_frustration`

---

### 5.3 token-service

**Purpose:** Mints short-lived LiveKit access tokens for browser/mobile callers.

**Port:** 8107
**Key Dependencies:** `livekit-api`, `fastapi`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/token` | Mint 1-hour room-join JWT |
| POST | `/client-events` | Mirror browser call progress to backend logs |

#### Token Generation
- Uses `livekit.api.AccessToken`
- Grants: `room_create=True`, `room_join=True`, `room=<room_name>`
- Optional `RoomConfiguration` with `RoomAgentDispatch` for named agent dispatch
- 1-hour TTL
- CORS configured for widget origins

---

### 5.4 client-widget

**Purpose:** React/TypeScript voice client widget — browser-based calling.

**Tech:** React 19, Vite 6, `livekit-client`, TypeScript

#### Files
- `src/App.tsx` — Main component with call flow: idle → connecting → connected/error
  - Fetches token from `token-service`
  - Connects to LiveKit room
  - Renders remote audio track
  - Mirrors events to `/client-events` for debugging
- `src/main.tsx` — React DOM entry
- `src/styles.css` — Styling
- `vite.config.ts` — Dev server on port 5173

---

### 5.5 supervisor-dashboard

**Purpose:** React/TypeScript supervisor/admin dashboard.

**Tech:** React 19, Vite 6, TypeScript

#### Files
- `src/api.ts` — API client for `business-api` endpoints (type-safe fetch)
- `src/types.ts` — TypeScript interfaces matching Pydantic models
- `src/components/EscalationQueue.tsx` — Escalation queue view
- `src/components/KpiPanel.tsx` — KPI display (containment/escalation rates)
- `src/components/SessionInspector.tsx` — Session transcript + sentiment detail
- `vite.config.ts` — Dev server on port 5174

---

## 6. Services — Detailed Breakdown

### 6.1 context-service

**Purpose:** Customer-360 system of record. Backed by PostgreSQL via shared `persistence` package.

**Port:** 8101
**Dependencies:** `sqlalchemy`, `cache`, `service-auth`, `persistence`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/internal/context/resolve?msisdn=...` | MSISDN → canonical UUIDs (customer_id, subscription_id) |
| GET | `/context/{msisdn}` | Customer-360 snapshot |
| POST | `/verify-identity` | Server-side step-up check (last 4 of national ID) |
| GET | `/billing/{customer_id}/invoices` | Customer invoices |
| GET | `/balance/{customer_id}` | Prepaid balance |

#### Key Components
- **`mapping.py`** — Pure mapping helpers (no DB dependencies):
  - `invoice_status()` — Maps raw status to open/paid/overdue
  - `account_age_days()` — Derives account age
  - `verify_answer()` — Checks last 4 digits of national ID
  - `to_megabytes()` — Normalizes data balance
- **`repositories.py`** — `CrmRepository` with methods:
  - `resolve_identity(msisdn)` → (Customer, Subscription) | None
  - `build_customer360(msisdn)` → Customer360 DTO
  - `verify_identity(customer_id, answer)` → bool
  - `get_invoices(customer_id)` → list of Invoice DTOs
  - `get_balance(customer_id)` → Balance DTO | None
- **`schemas.py`** — Pydantic models: `Customer360`, `ResolveIdentityResponse`, `VerifyIdentityRequest/Response`, `Invoice`, `InvoiceListResponse`, `Balance`
- **Cache**: Redis-backed via `cache` package; caches identity resolution for `CACHE_TTL_SECONDS`

---

### 6.2 knowledge-service

**Purpose:** RAG over the documentation corpus + vector store (Qdrant).

**Port:** 8102
**Dependencies:** `httpx`, `service-auth`, `domain-core`, optional `qdrant-client`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/search` | Return ranked, source-attributed passages for an English query |

#### Key Components
- **`corpus.py`** — Single English knowledge corpus with 5 documents:
  - Forfait Flexi postpaid plan (25 TND, 20 GB, USSD *111#)
  - Activate international roaming (*140#)
  - Mobile data troubleshooting (APN, airplane mode)
  - Invoice and billing cycle (*888#)
  - Change your mobile plan (next cycle)
- **`retriever.py`** — Two implementations:
  - `LexicalRetriever` (default): Term-overlap scoring, no external dependencies
  - `QdrantRetriever` (optional): `qdrant-client` behind `CONNECTOR_MODE=live`, embedding-based search
- **`schemas.py`** — `SearchRequest(query, top_k)`, `SearchResponse(passages)`, `PassageModel(text, source, score)`

---

### 6.3 decision-service

**Purpose:** Candidate-action ranking with confidence scoring.

**Port:** 8103
**Dependencies:** `service-auth`, `domain-core`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/recommend` | Rank a candidate action + confidence + rationale |

#### Scoring Logic (`scorer.py`)
- Known actions catalog: `EXECUTE_PAYMENT`, `PAYMENT_DEFERRAL`, `UNBLOCK_SIM`, `REPLACE_SIM`, `REACTIVATE_SIM`, `TOP_UP`, `CHANGE_PLAN`, `ACTIVATE_ROAMING`
- Deterministic rules:
  - Unknown action → confidence 0.2
  - Known + context sufficient → confidence 0.9
  - Known + identity not verified → confidence 0.6
- Returns: `{action, confidence, rationale}`

---

### 6.4 policy-service

**Purpose:** Mandatory, audited verdict checkpoint. Returns AUTHORIZED / REFUSED / ESCALATE.

**Port:** 8104
**Dependencies:** `sqlalchemy`, `service-auth`, `domain-core`, `audit-trail`, `persistence`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/evaluate-action` | Evaluate an action → verdict + rule_id + justification + verdict_id |
| POST | `/evaluate-response` | Guardrail an outbound response |
| GET | `/audit/verify` | Audit-chain integrity check |

#### Rule Engine (`rules/`)
Each rule evaluates a specific policy dimension:

| Rule File | Rule | Logic |
|---|---|---|
| `base.py` | `BaseRule` | Abstract base class with `evaluate()` and `domain` property |
| `payment.py` | `PaymentRule` | Payment cap: max 200 TND per transaction (configurable via `POLICY_PAYMENT_CAP_TND`) |
| `deferral.py` | `DeferralRule` | Deferral eligibility: min account age 180 days, max 2 per year, unpaid threshold 150 TND |
| `sim.py` | `SimRule` | SIM operations: requires identity verified, max 3 unblocks per 30 days |
| `mandatory_escalation.py` | `MandatoryEscalationRule` | Always triggers escalation for fraud-suspected or VIP customers |
| `outbound.py` | `OutboundRule` | Response guardrail: blocks PII leakage, excessive promises, unverified amounts |

**Service Layer** (`service.py`):
- `evaluate_action()`: Runs all applicable rules, collects verdicts
  - All AUTHORIZED → AUTHORIZED
  - Any ESCALATE → ESCALATE
  - Any REFUSED → REFUSED
- `evaluate_response()`: Runs outbound guardrails on agent responses
- Every verdict is persisted to `policy_verdicts` table and audit chain atomically
- Returns `verdict_id` which must be passed to execution-service

**Config** (`config.py`):
- `PolicyThresholds`: payment_cap_tnd, deferral_min_age_days, deferral_max_per_year, deferral_unpaid_threshold_tnd

---

### 6.5 execution-service

**Purpose:** Idempotent dispatch of authorized actions. Actions + audit persisted to PostgreSQL.

**Port:** 8105
**Dependencies:** `sqlalchemy`, `integration-adapters`, `service-auth`, `domain-core`, `audit-trail`, `persistence`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/execute` | Dispatch an AUTHORIZED action idempotently |
| GET | `/audit/verify` | Audit-chain integrity check |

#### Execution Flow (`service.py`)
1. Look up `idempotency_key` — if exists, return replay with same reference
2. INSERT pending `action_ledger` row (UNIQUE constraint on `idempotency_key` enforces at-most-once)
3. Dispatch via `executor.dispatch()` (mock or live)
4. Mark `succeeded`, set `adapter_reference`
5. Append audit entry via `PgAuditLedger`
6. Project domain effect (`projections.py`) in a SAVEPOINT

**Executor** (`executor.py`):
- Mock mode: generates deterministic prefixed references (`PAY-`, `SIM-`, `DEF-`, etc.)
- Live mode: routes through `integration-adapters` (billing, OCS, payment)
- Reference prefix mapping:
  - `EXECUTE_PAYMENT` → `PAY-`, target "billing"
  - `PAYMENT_DEFERRAL` → `DEF-`, target "billing"
  - `UNBLOCK_SIM` / `REPLACE_SIM` / `REACTIVATE_SIM` → `SIM-`, target "sim"
  - `TOP_UP` → `TOP-`, target "ocs"
  - `CHANGE_PLAN` → `PLN-`, target "provisioning"
  - `ACTIVATE_ROAMING` → `ROAM-`, target "provisioning"

**Projections** (`projections.py`):
- Maps action types to domain table projections:
  - `EXECUTE_PAYMENT` → `billing.payments`
  - `PAYMENT_DEFERRAL` → `billing.payment_plans`
  - `TOP_UP` → `ocs.recharges`
  - `UNBLOCK_SIM` / `REACTIVATE_SIM` → `sim.block_unblock_cases`
  - `CHANGE_PLAN` / `ACTIVATE_ROAMING` → `provisioning.*`
- Each projection carries `idempotency_key` and `policy_verdict_id`
- Runs in SAVEPOINT — projection failure never loses the action ledger or audit chain

---

### 6.6 notification-service

**Purpose:** Outbound written confirmations (SMS/WhatsApp/Email), localized + PII-masked.

**Port:** 8106
**Dependencies:** `service-auth`, `persistence`, `pii-shield`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/notify` | Send one localized written confirmation |
| GET | `/sent` | List confirmations sent so far (demo/inspection) |

#### Key Components
- **`channels.py`** — Channel strategy classes:
  - `ConsoleChannel` (mock/demo): Logs to console
  - `SmsChannel`: Twilio SMS (live)
  - `WhatsAppChannel`: Twilio WhatsApp (live)
  - `EmailChannel`: SendGrid/SMTP (live)
  - `NullChannel`: No-op fallback
  - `ChannelRouter`: Routes by channel type from `NOTIFICATION_CHANNEL` env
- **`templates.py`** — Localized templates (FR/AR/EN):
  - `ticket_created`: Confirmation with ticket ID
  - `payment_received`: Payment receipt with amount + reference
  - `deferral_granted`: Deferral confirmation
  - `callback_scheduled`: Callback time confirmation
  - `transfer_to_human`: Escalation notification
  - `consent_recorded`: Recording consent confirmation
  - `freeform`: Free-form message
- **`service.py`** — `NotificationService`:
  - `notify()`: Selects channel, renders template (PII-masked), sends, logs to DB
  - Tracks sent count via `sent` counter
- **`schemas.py`** — `NotifyRequest(customer_id, to, channel, template, language, params)`, `NotifyResponse(sent, channel, message_id)`

---

## 7. MCP Servers — Detailed Breakdown

### 7.1 ai-knowledge-rag

**Purpose:** Internal MCP server exposing `knowledge_search` (RAG/FAQ). Read-only, low-risk, reusable.

**Port:** 8201
**Dependencies:** `mcp`, `httpx`

#### Tools
| Tool | Description | Returns |
|---|---|---|
| `knowledge_search(query, top_k)` | Search the telecom knowledge base | List of `{text, source, score}` |

**Architecture:** Thin proxy to `knowledge-service:8102/search`. Every persona may call this tool.

### 7.2 messaging-gateway

**Purpose:** MCP server for outbound messaging (SMS/WhatsApp). Placeholder for Phase 9.

**Port:** 8203
**Dependencies:** `mcp`, `httpx`

#### Tools
| Tool | Description |
|---|---|
| `send_sms(to, message)` | Send SMS via notification-service |
| `send_whatsapp(to, message)` | Send WhatsApp via notification-service |

**Note:** The README documents an architectural caution — sending is a sensitive side-effect that should live in the notification-service. The MCP server exists for reuse by non-agent consumers.

### 7.3 ticketing-glpi

**Purpose:** Internal MCP server for GLPI ticket lifecycle (create/status/resolve/lookup).

**Port:** 8202
**Dependencies:** `mcp`, `httpx`, `persistence`

#### Tools
| Tool | Description |
|---|---|
| `create_ticket(customer_id, subject, description, language, category)` | Open a support ticket + send SMS confirmation |
| `get_ticket_status(ticket_id)` | Look up ticket status (mirror first, mock fallback) |
| `resolve_ticket(ticket_id, resolution)` | Resolve/close a ticket |
| `lookup_tickets(customer_id)` | List customer's tickets |

#### Key Components
- **`adapters/glpi_client.py`**: Dual mock/live implementation:
  - `MockGlpiClient`: In-memory ticket store
  - `LiveGlpiClient`: Real GLPI REST API client (initSession, Ticket CRUD)
  - `get_glpi_client()` factory: Live when `CONNECTOR_MODE=live` + GLPI credentials set
- **`adapters/mirror.py`**: Postgres mirror of GLPI tickets:
  - `mirror_create()`: Insert mirror row (idempotent on `glpi_ticket_id`)
  - `mirror_resolve()`: Mark mirror row resolved
  - `read_status()`: Read mirror view
  - `read_for_customer()`: List customer's mirrored tickets
  - Best-effort, gated on `DATABASE_URL`
- **`tools/glpi_ticket_ops.py`**: Tool implementations that combine mock/live client + mirror + notification

---

## 8. Packages — Detailed Breakdown

### 8.1 domain-core
**Purpose:** Pure domain entities, value objects, and ports. No framework, no vendor SDK.

**Entities:** `Client`, `Intent`, `Turn`, `Conversation`, `Decision`, `PolicyVerdict`, `Action`, `Ticket`, `EscalationCase`, `ConsentRecord`, `AuditEntry`

**Value Objects:** `Language(FR/AR/EN)`, `Channel(VOICE/CHAT/WHATSAPP/SMS/EMAIL)`, `Verdict(AUTHORIZED/REFUSED/ESCALATE)`, `Sentiment(SATISFIED/NEUTRAL/ANNOYED/ANGRY)`, `EscalationReason`, `Msisdn`, `Money`, `IdempotencyKey`

**Ports (12 interfaces):** `AuditPort`, `BalancePort`, `BillingPort`, `CrmPort`, `DecisionPort`, `ExecutionPort`, `KnowledgePort`, `NmsPort`, `NotificationPort`, `PaymentPort`, `PolicyPort`, `TicketingPort`

**Errors:** `DomainError`, `PolicyDeniedError`, `EscalationRequiredError`, `IdentityVerificationError`, `ExternalSystemUnavailableError`

### 8.2 persistence
**Purpose:** Shared SQLAlchemy 2.0 layer. Postgres-backed with Alembic migrations.

**Models (12 schemas):**
- `crm`: Customer, Subscription, ConsentRecord, CustomerInteraction
- `billing`: Account, Invoice, InvoiceItem, Payment, PaymentPlan
- `ocs`: BalanceAccount, Recharge, UsageEvent
- `sim`: SimProfile, BlockUnblockCase, PukRecord, SwapRequest
- `provisioning`: ProvisioningRequest, PlanChangeHistory
- `conversation`: CallSession, Turn, SentimentSample, EscalationCase, CallbackSchedule
- `execution`: ActionLedger
- `policy`: PolicyVerdict
- `audit`: AuditLedgerEntry, PiiTokenMap
- `ticketing`: Ticket
- `reference`: BusinessRule, ReferenceEntry
- `notification`: NotificationLog

**Engine:** `engine.py` — sync SQLAlchemy engine from `DATABASE_URL`. `session_scope()` context manager. `get_session()` FastAPI dependency.

**Base:** `base.py` — Custom declarative base with:
- UUID primary keys
- `created_at`/`updated_at` timestamp mixins
- Soft-delete mixin (optional)
- Naming convention for indexes/constraints

**Util:** `to_uuid()`, `require_uuid()` — UUID coercion helpers

**Alembic Migrations (8 versions):**
- `0001`: Extensions (uuid-ossp, pgcrypto), 12 schemas, crm/billing/ocs tables, `set_updated_at` trigger, `v_subscription_live` view
- `0002`: Safety core — policy_verdicts, action_ledger, audit_ledger, pii_token_map
- `0003`: Conversation — call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules
- `0004`: Domain writes — billing.payments/plans, ocs.recharges, sim.block_unblock_cases
- `0005`: Ticketing + notifications — ticketing.tickets, notification.notification_log + provisioning.plan_change_history
- `0006`: Reference — business_rules, reference_entries
- `0007`: OSS provisioning — provisioning_requests + sim.sim_profiles/puk_records/swap_requests
- `0008`: GIN indexes — full-text search indexes on conversation.turns and ticketing.tickets

**Seeds:**
- `seed_pilot.py`: 3 canonical callers with real TND amounts:
  - Karim Amiri (+21620155320, FR, 73.900 TND overdue)
  - Yousra Ben Ali (+21629744108, VIP, AR, postpaid)
  - Amine Kacem (+21655012345, prepaid, 12.450 TND balance)
- `seed_reference.py`: Reference data (business rules catalog, plan offerings)

### 8.3 audit-trail
**Purpose:** Append-only, hash-chained audit ledger.

**In-Memory:** `AuditLedger` — list-based for tests
**Postgres-Backed:** `PgAuditLedger` — advisory-lock-serialized, hash chain over `audit.audit_ledger`

**Hash Function:** `sha256(previous_hash | canonical_json(payload) | timestamp)`
**Chain Verify:** Recomputes entire chain; any retroactive edit breaks the hash.

### 8.4 cache
**Purpose:** Optional Redis cache. NullCache when Redis is unavailable.

**Implementations:**
- `NullCache`: Every read misses, writes are no-ops, idempotency never blocks
- `RedisCache`: Thin wrapper over redis-py

**Key Methods:** `get()`, `set()`, `delete()`, `add_if_absent()` (for idempotency)

### 8.5 integration-adapters
**Purpose:** Per-legacy-system adapters implementing domain-core ports. Mock by default.

**Factory Pattern:** `CONNECTOR_MODE` env var (mock|live) + per-adapter URL env vars.

| Adapter | Port | Mock | Live |
|---|---|---|---|
| `billing_adapter.py` | `BillingPort` | Returns empty invoices, synthetic references | Calls BILLING_ADAPTER_URL |
| `ocs_adapter.py` | `BalancePort` | Zero balance, synthetic refs | Calls OCS_ADAPTER_URL |
| `payment_adapter.py` | `PaymentPort` | Synthetic PAY- refs | Calls PAYMENT_ADAPTER_URL |
| `crm_adapter.py` | `CrmPort` | Returns None | Calls CRM_ADAPTER_URL |
| `nms_adapter.py` | `NmsPort` | "operational" status | Calls NMS_ADAPTER_URL |
| `glpi_adapter.py` | `TicketingPort` | Synthetic GLPI tickets | Calls GLPI_ADAPTER_URL |

### 8.6 notification-client
**Purpose:** NotificationPort implementation that posts to notification-service over HTTP.

### 8.7 object-storage
**Purpose:** Optional MinIO/S3 object storage for call recordings. NullStore when unconfigured.

### 8.8 observability-kit
**Purpose:** Shared OpenTelemetry tracer/meter setup.

**Instruments:**
- `record_ttfa()` — Time to first audio
- `record_ttft()` — Time to first token
- `incr_escalation()` — Escalation counter
- `incr_fallback()` — Provider fallback counter

**Design:** Dependency-optional (no-ops if OTel SDK absent). Endpoint-gated (only when `OTEL_EXPORTER_OTLP_ENDPOINT` set).

### 8.9 pii-shield
**Purpose:** PII masking across the platform.

**Patterns masked:** Phone numbers (`+216XXXXXXXX`), email addresses, national ID numbers (8 digits), credit card numbers, full names (configurable patterns).

### 8.10 service-auth
**Purpose:** Internal API key authentication for service-to-service calls.

**Key functions:**
- `internal_headers()` — Returns `{"X-API-Key": INTERNAL_API_KEY}` dict
- `require_internal_key()` — FastAPI dependency that validates `X-API-Key` header

---

## 9. Infrastructure & Deployment

### Docker Compose (`infra/docker-compose/`)

#### Infrastructure Stack (`docker-compose.yml`)
| Service | Image | Port | Purpose |
|---|---|---|---|
| `livekit-server` | `livekit/livekit-server:v1.8.4` | 7880-7882 | Self-hosted LiveKit (opt-in profile) |
| `redis` | `redis:7.4-alpine` | 6379 | Cache + idempotency |
| `postgres` | `postgres:16-alpine` | 5432 | Primary data store |
| `qdrant` | `qdrant/qdrant:v1.12.5` | 6333 | Vector store for RAG |
| `minio` | `minio/minio:RELEASE.2024-12-18` | 9000-9001 | Object storage (recordings) |
| `otel-collector` | `otel/opentelemetry-collector-contrib:0.116.1` | 4317-4318 | Tracing/metrics collection |

#### App Stack (`docker-compose.apps.yml`)
11 services managed together:
- 8 domain services (context, knowledge, decision, policy, execution, notification, token, business-api)
- 3 MCP servers (ai-knowledge-rag, ticketing-glpi, messaging-gateway)
- 1 agent-worker

All share the repo root as Docker build context, use per-service Dockerfiles, and share the `.env` file.

### Nginx Gateway (`infra/docker-compose/nginx/nginx.conf`)
- Routes to all 8 services by path prefix
- WebSocket upgrade for LiveKit
- MinIO S3-compatible API proxy
- Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
- Listen port 8080

### Helm Charts

#### `infra/helm/telecom-platform/`
Full Kubernetes deployment:
- `namespace.yaml` — Platform namespace
- `services.yaml` — All 8 domain services + 3 MCP servers + agent-worker
- `gateway.yaml` — Nginx ingress gateway
- `infra.yaml` — Redis, Postgres, Qdrant, MinIO
- `otel.yaml` — OpenTelemetry collector
- `secrets.yaml` — Secret definitions
- `_helpers.tpl` — Template helpers
- `values.yaml` — Configurable values

#### `deploy/helm/telecom-agent/`
Simpler Helm chart for the agent component only:
- `deployment.yaml` — Agent-worker deployment
- `values.yaml` — Configurable values

### Deploy Configurations

#### Backup (`deploy/backup/`)
- `backup.sh` — Postgres backup script
- `restore.sh` — Postgres restore script
- `verify_audit_chain.py` — Audit chain verification tool

#### Gateway (`deploy/gateway/`)
- `docker-compose.gateway.yml` — Gateway as standalone compose service
- `nginx.conf` — Same as infra nginx config

#### OpenTelemetry (`deploy/otel/`)
- `docker-compose.yml` — OTel stack (collector + prometheus)
- `otel-collector-config.yaml` — Collector configuration
- `prometheus.yml` — Prometheus scrape config

#### Postgres (`deploy/postgres/`)
- `docker-compose.yml` — Standalone Postgres with healthcheck

#### Secrets (`deploy/secrets/`)
- `docker-compose-secrets.yml` — HashiCorp Vault integration
- `.env.example` — POINTER to root `.env.example` (single source of truth)
- `README.md` — Secrets management docs

---

## 10. Scripts & Automation

| Script | Language | Purpose |
|---|---|---|
| `health_check.py` | Python | Probe all 11 services' /health endpoints + TCP probes for MCPs |
| `run_tests.py` | Python | Run offline test suite across all packages/services with correct PYTHONPATH |
| `install_dev.ps1` | PowerShell | Full dev environment install (packages, services, MCPs, frontends) |
| `start_dev.ps1` | PowerShell | Start infra containers + migrate + seed + honcho |
| `start_dev_containers.ps1` | PowerShell | Start everything in Docker containers |
| `stop_dev.ps1` | PowerShell | Stop all containers |
| `fix_frontend_deps.sh` | Bash | Fix frontend dependency issues (Rollup OS mismatch) |

---

## 11. Database Schema (Alembic Migrations)

### Migration 0001 — Initial CRM / Billing / OCS
- Extensions: `uuid-ossp`, `pgcrypto`
- 12 schemas created: `crm`, `billing`, `ocs`, `sim`, `provisioning`, `conversation`, `execution`, `policy`, `audit`, `ticketing`, `reference`, `notification`
- Tables: `crm.customers`, `crm.subscriptions`, `crm.consent_records`, `crm.customer_interactions`, `billing.accounts`, `billing.invoices`, `billing.invoice_items`, `ocs.balance_accounts`
- Trigger: `set_updated_at()` on mutable tables
- View: `crm.v_subscription_live` (read-through view of active subscriptions)

### Migration 0002 — Safety Core
- `policy.policy_verdicts` — Verdict records with FK to sessions
- `execution.action_ledger` — Idempotent action log with UNIQUE `idempotency_key`, FK to `policy_verdicts`
- `audit.audit_ledger` — Hash-chained audit entries (BIGINT IDENTITY seq, CHAR(64) hashes)
- `audit.pii_token_map` — PII token mapping table
- `action_ledger.updated_at` trigger

### Migration 0003 — Conversation
- `conversation.call_sessions` — Call records with duration, disposition, frustration
- `conversation.turns` — Per-turn transcripts (UNIQUE session_id + turn_index + speaker)
- `conversation.sentiment_samples` — Sentiment scores per turn
- `conversation.escalation_cases` — Escalation records with JSONB dossier
- `conversation.callback_schedules` — Scheduled callbacks

### Migration 0004 — Domain Writes
- `billing.payments` — Payment records with gateway reference
- `billing.payment_plans` — Deferral/installment plans with policy_verdict_id
- `ocs.recharges` — Top-up transactions
- `sim.block_unblock_cases` — SIM action records with verdict linkage

### Migration 0005 — Ticketing + Notifications
- `ticketing.tickets` — GLPI ticket mirror (glpi_ticket_id, customer_id, subject, category, status, priority)
- `notification.notification_log` — Sent notification records
- `provisioning.plan_change_history` — Plan change audit trail

### Migration 0006 — Reference
- `reference.business_rules` — Versioned Policy rule definitions
- `reference.reference_entries` — Reference data catalog

### Migration 0007 — OSS Provisioning
- `provisioning.provisioning_requests` — Provisioning request records
- `sim.sim_profiles`, `sim.puk_records`, `sim.swap_requests` — SIM inventory

### Migration 0008 — GIN Indexes
- Full-text search GIN indexes on `conversation.turns.transcript_masked`
- Full-text search GIN indexes on `ticketing.tickets.subject` and `description`

---

## 12. Testing Strategy

### Offline Unit Tests (no DB required — run via `make test`)

| Suite | Files | Tests | Coverage |
|---|---|---|---|
| `packages/audit-trail` | `test_chain.py` | 3 | Hash chain determinism, chain integrity, tamper detection |
| `packages/service-auth` | `test_service_auth.py` | — | Service auth validation |
| `packages/cache` | `test_cache.py` | 2 | NullCache defaults and semantics |
| `packages/object-storage` | `test_store.py` | 2 | NullStore defaults and semantics |
| `packages/integration-adapters` | `test_adapters.py` | 4 | Factory defaults to mock, live without URL falls back, mock honors ports |
| `packages/persistence` | `test_migrations.py` | — | Migration application verification |
| `packages/observability-kit` | `test_telemetry.py` | — | Telemetry configuration |
| `services/context-service` | `test_mapping.py` (4) | 4 | Invoice status, account age, verify answer, to_megabytes |
| `services/knowledge-service` | `test_retriever.py` | — | Lexical retriever scoring |
| `services/decision-service` | `test_scorer.py` | 3 | Known/unknown actions, identity confidence |
| `services/policy-service` | `test_policy.py` | — | Policy rule evaluation |
| `services/execution-service` | `test_executor.py`, `test_projections.py` | 5 | Target domain mapping, reference prefixes, projection kinds, installment math |
| `services/notification-service` | `test_notification.py`, `test_multilingual.py` | — | Notification dispatch |
| `mcp-servers/ticketing-glpi` | `test_mirror.py` | 2 | Category normalization, mirror disabled fallback |
| `apps/business-api` | `test_kpis.py`, `test_security.py`, `test_integrity.py`, `test_retention.py` | 8 | KPI math, role hierarchy, integrity summary, retention cutoff |
| `apps/agent-worker` | `test_writer.py`, `test_customer_context.py`, `test_chaos_wiring.py`, `test_sentiment_scorer.py`, `test_multilingual.py` | — | Writer queue, context building, resilience wiring, sentiment scoring |

### Integration Tests (require Postgres)
- `services/context-service/tests/test_aggregator.py` — CrmRepository against real Postgres
- `apps/token-service/tests/test_token.py` — LiveKit JWT grant verification

### Load Tests (`tests/load/`)
- `loadtest.py` — Concurrent session simulation
- `soak.py` — Extended soak testing
- `README.md` — Load test documentation

### UAT Tests (`docs/compliance/UAT-PLAN.md`)
- Multilingual parity tests for FR/AR/EN
- End-to-end call flow scenarios

---

## 13. CI/CD Pipeline

**File:** `.github/workflows/ci.yml`

### Pipeline Stages
1. **Lint** — ruff check + mypy type checking
2. **Test** — Install all shared packages, run offline test suite across all packages/services
3. **DB Migrations** — Spin up Postgres, apply Alembic migrations, run seeds
4. **Docker Build (Services)** — Build and push all 8 service images to GHCR
5. **Docker Build (Apps)** — Build and push token-service, business-api, agent-worker
6. **Security Scan** — Trivy vulnerability scanning on all built images, upload SARIF results

---

## 14. Business Logic & Data Flow

### Call Lifecycle
```
1. Browser/mobile caller requests token from token-service
2. Caller connects to LiveKit room with minted JWT
3. LiveKit dispatches agent-worker to the room
4. server.py entrypoint:
   a. Builds SessionUserData with language
   b. Pre-fetches Customer-360 snapshot from context-service (if MSISDN known)
   c. Opens ConversationWriter (async, off-voice-path)
   d. Starts TriageAgent session
5. TriageAgent:
   a. Collects recording consent via ConsentTask
   b. Greets caller by name (if known) or generically
   c. Routes to appropriate agent (billing/technical/manager) or answers FAQ
6. Agent handles request:
   a. For sensitive actions (payment, SIM unblock, deferral):
      i. Identity verification (last 4 of national ID)
      ii. Decision service (rank action confidence)
      iii. Policy service (deterministic verdict)
      iv. Execution service (idempotent dispatch + audit)
      v. Domain projection (payment_plan, sim_case, etc.)
      vi. Written confirmation via notification-service
   b. For knowledge questions:
      i. knowledge_search via MCP → knowledge-service
   c. For escalations:
      i. Transfer to ManagerAgent
      ii. Create ticket via ticketing-glpi
      iii. Notification to caller with ticket reference
7. BaseAgent per-turn:
   a. Score sentiment → update frustration history
   b. Record turn + sentiment to conversation DB (off-path)
   c. Inject de-escalation note if frustration high
8. Call ends: finalize session record (duration, max frustration, disposition)
```

### Sensitive Action Flow (GuardedAction)
```
Agent Tool Call (e.g., make_payment)
  → ensure_identity_verified (step-up check)
  → execute_guarded_action:
     → decision_client.recommend(action_type, context)
     → if confidence < threshold: escalate
     → policy_client.evaluate_action(context)
     → if not AUTHORIZED: return verdict
     → execution_client.execute(idempotency_key, action_type, ..., policy_verdict_id)
        → execution-service:
           → Check idempotency key (replay if exists)
           → INSERT action_ledger (pending)
           → dispatch (mock or live adapter)
           → Mark succeeded
           → Append audit chain entry
           → Project domain effect (payment, sim_case, etc.)
           → Return reference
     → Return outcome to agent
```

### Policy Decision Matrix

| Rule | Condition | Verdict |
|---|---|---|
| **Payment Cap** | Amount > 200 TND | REFUSED |
| **Payment Cap** | Amount ≤ 200 TND | AUTHORIZED |
| **Deferral** | Account age < 180 days | REFUSED |
| **Deferral** | Already used 2 this year | REFUSED |
| **Deferral** | Unpaid amount > 150 TND | REFUSED |
| **Deferral** | All checks pass | AUTHORIZED |
| **SIM Unblock** | More than 3 unblocks in 30 days | REFUSED |
| **SIM Unblock** | Within limit | AUTHORIZED |
| **Mandatory Escalation** | Fraud suspected OR VIP | ESCALATE |
| **Outbound Guardrail** | Contains PII / excessive promises | REFUSED |
| **Policy Unavailable** | Service down | ESCALATE (fail-closed) |

### Identity Verification
- **Method:** Last 4 digits of national ID (CIN)
- **Secret never leaves context-service**: comparison is server-side
- **Step-up required before:** payment, deferral, SIM unblock, plan change
- **Storage:** `crm.customers.national_id` field

### Audit Chain
```
Genesis (0x0000...)
  → Entry 1: policy_verdict (session_id, verdict, rule_id)
    → Entry 2: execution_result (action_type, reference, idempotency_key)
      → Entry 3: consent_record (granted, consent_type)
        → ...
```

Each entry: `sha256(previous_hash | canonical_json(payload) | timestamp)`

Tamper: editing any entry breaks its hash → subsequent entries' `previous_hash` mismatch → `verify()` returns False.

---

## 15. Security Model

### Layers
1. **Inter-Service Auth** (`service-auth`): All domain services + MCP servers require `X-API-Key` header matching `INTERNAL_API_KEY` env var
2. **API RBAC** (`business-api/security.py`): 3-tier role hierarchy (conseiller → superviseur → administrateur), enforced via `X-Role` header
3. **Worker ↔ Service**: Typed HTTP clients carry `internal_headers()` on every request
4. **LiveKit Auth**: Short-lived JWT tokens (1 hour) minted by token-service
5. **CORS**: Token-service and business-api have explicit `allow_origins` from `CORS_ORIGINS` env
6. **PII Masking**: `pii-shield` masks sensitive data (phone numbers, national IDs, emails, credit cards) in logs and transcripts
7. **Fail-Close Policy**: Policy client returns ESCALATE on service error — never silently AUTHORIZEs
8. **Append-Only Audit**: Database roles should be `INSERT, SELECT` only on audit/verdict/action tables
9. **Secrets Management**: `deploy/secrets/` with Vault integration for production

---

## 16. Fixes Directory (Hot-Patch Overlay)

**Location:** `fixes/` directory mirrors the main project structure with corrected versions.

**Purpose:** A parallel fix-tree containing hot-patched versions of files from diagnostic resolution. Created during the code diagnostic phase to fix 11 identified issues.

**Key fixes in `fixes/`:**
- Fixed `pyproject.toml` files with correct dependency declarations (sqlalchemy, httpx)
- Fixed `main.py` files with merged `Depends` imports
- Updated `docker-compose.yml` and `docker-compose.apps.yml`
- Fixed `Makefile` and `Procfile` with correct paths
- Updated `health_check.py` and `run_tests.py` scripts
- Service `main.py` files with corrected FastAPI dependencies
- MCP server `pyproject.toml` with correct `mcp` version ranges

**Note:** The main project files in `services/`, `apps/`, `infra/`, etc. may already incorporate these fixes. The `fixes/` directory serves as a diagnostic overlay reference.

---

## 17. Documentation Inventory

| Document | Location | Content |
|---|---|---|
| **Architecture Blueprint** | `ALL_SYSTEM_ARCHITECTURE.md` | Full system architecture |
| **Phase-0 Decision Record** | `docs/architecture/phase-0-verification-gate/00-DECISION-RECORD.md` | Provider selection, language routing decisions |
| **Provider Matrix** | `docs/architecture/phase-0-verification-gate/verification/provider_matrix.py` | Machine-readable provider routing |
| **ADR Data Layer** | `docs/persistence/ADR-0001-data-layer.md` | Persistence architecture decision |
| **Persistence P1-P4** | `docs/persistence/PERSISTENCE-P{2-6}-README.md` | Per-phase persistence changes |
| **Compliance** | `docs/compliance/PILOT-READINESS.md` | Pilot readiness checklist |
| **Traceability** | `docs/compliance/TRACEABILITY.md` | Requirements traceability |
| **UAT Plan** | `docs/compliance/UAT-PLAN.md` | User acceptance test plan |
| **Patch Sets** | `docs/patches/PATCHSET-{1-4}-*.md` | Security, persistence, integration, infra patches |
| **Tester Report** | `docs/patches/TESTER-REPORT-RESOLUTION.md` | Tester report resolution |
| **Run Guide** | `docs/RUN.md`, `start_commands.md` | How to run the platform |
| **AI Model Inventory** | `docs/AI_MODEL_INVENTORY.md` | All AI models used |
| **System Codes** | `SYSTEM_CODES.md` | Error code reference |
| **Code Diagnostic** | `CODE_DIAGNOSTIC.md` | Diagnostic findings |
| **Diagnostic Resolution** | `DIAGNOSTIC-RESOLUTION.md` | Resolution of 11 diagnostic items |
| **Error Investigation** | `ERROR_INVESTIGATION.md` | Error root cause analysis |
| **Session Log Analysis** | `SESSION_LOG_ANALYSIS.md` | Session log patterns and analysis |
| **Startup Diagnostic** | `STARTUP_DIAGNOSTIC.md` | Startup sequence diagnostics |
| **Phase Docs** | `docs/phase-{7,8,9,10}/`, `docs/phases/PHASE-{11,12}-README.md` | Phase-specific documentation |

---

## Appendices

### A. Port Map

| Service | Port | Type |
|---|---|---|
| context-service | 8101 | HTTP REST |
| knowledge-service | 8102 | HTTP REST |
| decision-service | 8103 | HTTP REST |
| policy-service | 8104 | HTTP REST |
| execution-service | 8105 | HTTP REST |
| notification-service | 8106 | HTTP REST |
| token-service | 8107 | HTTP REST |
| business-api | 8108 | HTTP REST |
| ai-knowledge-rag MCP | 8201 | MCP Streamable HTTP |
| ticketing-glpi MCP | 8202 | MCP Streamable HTTP |
| messaging-gateway MCP | 8203 | MCP Streamable HTTP |
| LiveKit Server | 7880-7882 | WebSocket/WebRTC |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Qdrant | 6333 | Vector Store |
| MinIO | 9000-9001 | Object Storage |
| OTEL Collector | 4317-4318 | gRPC/HTTP Telemetry |

### B. Environment Variable Groups
- **Required:** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `ELEVEN_API_KEY`, `GOOGLE_API_KEY`, `DATABASE_URL`
- **Optional STT/TTS:** `AZURE_SPEECH_KEY`, `CARTESIA_API_KEY`, `GLADIA_API_KEY`
- **Optional LLM:** `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `GROQ_API_KEY`
- **Live Legacy Systems:** `BILLING_ADAPTER_URL`, `PAYMENT_ADAPTER_URL`, `OCS_ADAPTER_URL`, `CRM_ADAPTER_URL`, `NMS_ADAPTER_URL`, `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`
- **Messaging:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `SENDGRID_API_KEY`, `SMTP_HOST`
- **Infrastructure:** `REDIS_URL`, `QDRANT_URL`, `MINIO_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT`

### C. Key File References by Business Function

| Business Function | Key Files |
|---|---|
| Voice Pipeline Setup | `apps/agent-worker/src/server.py`, `providers/session_factory.py` |
| Call Recording Consent | `apps/agent-worker/src/tasks/consent_task.py` |
| Customer Identification | `services/context-service/src/context_service/repositories.py` (resolve_identity) |
| Billing/Payment | `apps/agent-worker/src/tools/billing_tools.py`, `agents/billing_agent.py` |
| Payment Processing | `apps/agent-worker/src/tasks/payment_confirm_task.py`, `tools/guarded_action.py` |
| SIM Management | `apps/agent-worker/src/tools/technical_tools.py` |
| Ticket Creation | `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` |
| Human Escalation | `apps/agent-worker/src/tools/escalation_tools.py`, `telephony/sip_transfer.py` |
| Knowledge Search | `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py` |
| Conversation Recording | `apps/agent-worker/src/conversation/writer.py` |
| Sentiment Analysis | `apps/agent-worker/src/sentiment/sentiment_scorer.py` |
| Audit Trail | `packages/audit-trail/src/audit_trail/ledger.py` |
| Policy Rules | `services/policy-service/src/policy_service/rules/` (6 rule files) |
| KPI Dashboard | `apps/business-api/src/business_api/kpis.py`, `repositories.py` |
| Database Migrations | `packages/persistence/alembic/versions/` (8 migration files) |
| CI/CD Pipeline | `.github/workflows/ci.yml` |

---

> **End of Report**
> 
> This report contains a complete reference of all code, configuration, business logic, and infrastructure for the Telecom AI Agent Platform.  
> For questions, contact the development team or refer to the issue tracker.
