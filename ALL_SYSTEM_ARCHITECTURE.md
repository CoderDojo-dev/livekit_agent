# Telecom AI Voice Agent — Complete System Architecture

## 1. Project Overview

A real-time, multilingual AI voice agent for telecom customer support. Callers speak in French, Arabic, or English; the system transcribes, understands intent via a primary LLM (Gemini 3.5 Flash) with fallback chain, executes guarded business actions (billing, SIM, ticketing), and speaks back — all in low-latency WebRTC via LiveKit.

**Architecture style:** Clean Architecture / Hexagonal + DDD + event-driven microservices.  
**Team:** Monorepo (no polyrepo).  
**Target:** Docker Compose on Linux; Windows dev via WSL 2 + Docker Desktop.

---

## 2. Directory Map

```
telecom-ai-agent-platform/
├── packages/           # 10 shared Python libraries (domain-core, persistence, etc.)
├── services/           # 6 FastAPI microservices (context, decision, policy, etc.)
├── apps/               # 5 deployable apps (agent-worker, token-service, business-api, 2 frontends)
├── mcp-servers/        # 3 MCP servers (knowledge RAG, GLPI ticketing, messaging)
├── infra/              # Docker Compose, Helm, LiveKit config
├── deploy/             # Production deployment (backup, gateway, OTEL, Postgres, secrets)
├── scripts/            # Dev/ops helpers (health_check.py, run_tests.py)
├── tests/              # Load/soak tests
├── docs/               # Architecture docs, ADRs, phase plans, runbook
├── fixes/              # Pending-fix copies for parallel work
├── .github/workflows/  # CI (ruff + mypy + pytest)
├── .env                # All 237 env vars (25 sections)
├── Makefile            # Dev orchestration (install, dev, up, rebuild, health)
├── Procfile            # Honcho multi-process dev runner
├── start.ps1           # Windows PowerShell Docker wrapper
└── pyproject.toml       # Root tooling config (ruff, mypy)
```

---

## 3. Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    apps/ [Deployable]                         │
│  agent-worker  token-service  business-api   2 React SPAs    │
├──────────────────────────────────────────────────────────────┤
│                  services/ [Domain Services]                  │
│  context → knowledge → decision → policy → execution → notif │
├──────────────────────────────────────────────────────────────┤
│               mcp-servers/ [Tool Servers]                    │
│  ai-knowledge-rag   ticketing-glpi   messaging-gateway       │
├──────────────────────────────────────────────────────────────┤
│              packages/ [Shared Libraries]                     │
│  domain-core  persistence  audit-trail  pii-shield           │
│  observability-kit  service-auth  cache  object-storage      │
│  notification-client  integration-adapters                    │
├──────────────────────────────────────────────────────────────┤
│              infra/ + deploy/ [Infrastructure]                │
│  Postgres 16  Redis 7  Qdrant  MinIO  OTEL  NGINX  Helm      │
└──────────────────────────────────────────────────────────────┘
```

**Port map:**

| Port | Component |
|------|-----------|
| 8101 | Context Service |
| 8102 | Knowledge Service |
| 8103 | Decision Service |
| 8104 | Policy Service |
| 8105 | Execution Service |
| 8106 | Notification Service |
| 8107 | Token Service |
| 8108 | Business API |
| 8201 | MCP — ai-knowledge-rag |
| 8202 | MCP — ticketing-glpi |
| 8203 | MCP — messaging-gateway |
| 7880-7882 | LiveKit Server |
| 5432 | Postgres |
| 6379 | Redis |
| 6333 | Qdrant |
| 9000/9001 | MinIO |
| 4317 | OTEL collector |
| 5173 | Supervisor Dashboard (Vite) |
| 5174 | Client Widget (Vite) |

---

## 4. Shared Libraries (`packages/`)

| Package | Role | Deps |
|---------|------|------|
| **domain-core** | Pure entities (`Client`, `Intent`, `Turn`, `Action`), value objects (`Language`, `Money`, `Verdict`), and 12 port interfaces (DIP). Zero framework deps. | — |
| **persistence** | SQLAlchemy models (14 model modules), engine/session factory, Alembic migrations (8 versions). | `sqlalchemy`, `psycopg`, `alembic` |
| **audit-trail** | Append-only hash-chained audit ledger (`PgAuditLedger`). | `domain-core`, `persistence` |
| **pii-shield** | PII detection/masking/pseudonymization. | — |
| **observability-kit** | OpenTelemetry tracer/meter, TTFA/TTFT recording. | `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc` |
| **service-auth** | Inter-service `X-API-Key` auth for FastAPI + httpx. | `fastapi` |
| **cache** | Optional Redis cache (no-op when Redis unavailable). | `redis` |
| **object-storage** | Optional MinIO/S3 for call recordings. | `minio` |
| **notification-client** | SMS/Email/WhatsApp abstraction (Strategy pattern). | `httpx`, `domain-core` |
| **integration-adapters** | Per-legacy-system adapters (CRM, billing, OCS, NMS, payment, GLPI) with mock/live switching. | `domain-core`, `httpx` |

---

## 5. Domain Services (`services/`) — The Business Logic Layer

All are FastAPI apps with `/health` + domain endpoints. Run in Docker or via Honcho.

### 5.1 Context Service (8101)
Customer-360 identity system of record. `GET /context/{msisdn}` returns `CustomerContext` snapshot from Postgres. Used by agent-worker on every call to personalize greeting and enable identity-gated actions.

### 5.2 Knowledge Service (8102)
RAG over telecom documentation corpus via Qdrant vector store. `POST /knowledge/search` returns semantically similar FAQ chunks. Read-only.

### 5.3 Decision Service (8103)
Candidate-action ranking + confidence scoring. `POST /decision/recommend` proposes the best action given caller context. Pure stateless scoring.

### 5.4 Policy Service (8104)
Mandatory, audited verdict checkpoint. `POST /policy/evaluate-action` applies hard-coded business rules (payment caps, deferral limits, SIM policies) and returns AUTHORIZED / REFUSED / ESCALATE. Verdicts are persisted and audit-chained. Rules live in `services/policy-service/src/policy_service/rules/`.

### 5.5 Execution Service (8105)
Idempotent action ledger. `POST /execution/execute` performs the action via integration-adapters (CRM, billing, OCS, etc.) and records the result with the policy `verdict_id` for audit trail. Idempotency key = SHA-256(session_id, action_type).

### 5.6 Notification Service (8106)
Outbound written confirmations (SMS/WhatsApp/Email). `POST /notification/notify` renders localized templates, PII-masks content, and sends via Twilio/SendGrid/SMTP. Mock when service keys absent.

**Service dependency chain (read path):** Context → Knowledge  
**Service dependency chain (write path):** Decision → Policy → Execution → Notification

---

## 6. `apps/agent-worker/` — Real-Time Orchestrator

The heart of the system. A LiveKit Agents worker connecting to LiveKit Cloud (or self-hosted). **Zero business logic** — all tools delegate to domain services.

### 6.1 Startup Sequence (`src/server.py`)

```
load_dotenv() → install_pii_masking() → build AgentServer
  └─ on RTC session:
      1. build_agent_session(language)
         → STT: Deepgram (primary), Gladia (opt), Azure (opt)
         → LLM: Google Gemini (primary), NVIDIA NIM (opt), OpenAI (opt), Groq (opt)
         → TTS: ElevenLabs (opt), Cartesia (opt)
         → VAD: Silero (local)
         → turn_detection: "stt" (STT end-of-utterance)
      2. _prefetch_user_data(language)
         → GET /context/{msisdn} → CustomerContext
      3. _open_conversation()
         → ConversationWriter (off-path queue → Postgres)
      4. session.start(agent=TriageAgent(language))
```

### 6.2 Provider Chain (`src/providers/`)

Every provider chain uses LiveKit's `FallbackAdapter` for automatic degradation:

| Chain | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|-------|---------|------------|------------|------------|
| **STT** | Deepgram (nova-3) | Gladia (opt) | Azure (opt) | — |
| **LLM** | Google Gemini 3.5 Flash | NVIDIA NIM (opt) | OpenAI GPT-4o-mini (opt) | Groq llama-3.1 (opt) |
| **TTS** | ElevenLabs Flash v2.5 (opt) | Cartesia sonic-2 (opt) | — | — |

Each fallback is skipped when its API key is absent or empty.

#### 6.2.1 LLM Adapter Details

- **`llm.py`**: Builds the `FallbackAdapter` chain — `google.LLM(model=primary_model)` → `NvidiaLLM` → `openai.LLM(model=fallback_model)` → `GroqLLM`
- **`nvidia_adapter.py`**: Subclasses `openai.LLM` with NVIDIA NIM base URL (`https://integrate.api.nvidia.com/v1`). Working as of model ID fix.
- **`groq_adapter.py`**: Subclasses `openai.LLM` with Groq base URL (`https://api.groq.com/openai/v1`). Working as of model ID fix.
- **Chaos toggle**: `CHAOS_BREAK_LLM=true` injects an invalid model ID to test fallback behavior.

#### 6.2.2 STT/TTS/VAD Details

- **`stt.py`**: `deepgram.STT(model="nova-3")` primary. Gladia/Azure added when respective API keys present.
- **`tts.py`**: ElevenLabs primary (skipped if no `ELEVEN_API_KEY`). Cartesia fallback (skipped if no `CARTESIA_API_KEY`). Azure final fallback (skipped if no `AZURE_SPEECH_KEY`).
- **`vad.py`**: Silero VAD (local, no API key). `min_silence_duration` from `VAD_MIN_SILENCE` (default 250ms).
- **`turn_detection.py`**: Returns `"stt"` — uses STT end-of-utterance as turn signal. Changed from `MultilingualModel()` to fix cloud compatibility.
- **`noise_cancellation.py`**: Optional BVC noise cancellation from livekit-plugins-noise-cancellation. Off by default.

### 6.3 Agent Personas (`src/agents/`)

All inherit from `BaseTelecomAgent` (extends `livekit.agents.Agent`). Hand-off via route tools returning `(NextAgent, transition_line)` tuples.

| Agent | File | Role | Key Tools |
|-------|------|------|-----------|
| **TriageAgent** | `triage_agent.py` | Default starting persona. Consent + greeting + FAW + routing. | `request_clarification`, `route_to_billing`, `route_to_technical`, `escalate_to_manager`, `knowledge_search` (MCP) |
| **BillingAgent** | `billing_agent.py` | Invoice/balance inquiries + guarded payment/deferral. | `get_invoice_summary`, `get_balance_summary`, `make_payment`, `request_payment_deferral`, `escalate_to_manager` |
| **TechnicalAgent** | `technical_agent.py` | SIM/network/connectivity. Identity-gated SIM unblock + ticketing. | `unblock_sim`, `create_ticket` (MCP), `knowledge_search` (MCP) |
| **AccountServicesAgent** | `account_services_agent.py` | Plan consultation/change, prepaid top-up, roaming toggle. | `get_plan_details`, `change_plan`, `top_up`, `toggle_roaming` |
| **ManagerAgent** | `manager_agent.py` | Escalation target. Human transfer or callback scheduling. | `transfer_to_human`, `create_ticket` (MCP) |

### 6.4 Tools (`src/tools/`)

All `@function_tool()` decorated — thin facades delegating to HTTP clients. Zero business logic.

| Tool File | Purpose |
|-----------|---------|
| `routing_tools.py` | `route_to_billing()`, `route_to_technical()` — agent hand-off |
| `escalation_tools.py` | `escalate_to_manager()` — records escalation, hands off to ManagerAgent |
| `billing_tools.py` | `get_invoice_summary()`, `get_balance_summary()` via ContextClient |
| `account_tools.py` | `get_plan_details()`, `change_plan()`, `top_up()`, `toggle_roaming()` |
| `technical_tools.py` | `diagnose_data_issue()`, `unblock_sim_pin()`, `check_network_status()` (stubs) |
| `clarification_tools.py` | `request_clarification()` — counts attempts, auto-escalates after 2 failures |
| `guards.py` | `ensure_identity_verified()` — runs IdentityVerificationTask inline |
| `guarded_action.py` | `execute_guarded_action()` — Decision → Policy → Execution façade |
| `outcomes.py` | Outcome dict factories: `executed()`, `refused()`, `escalate()`, `failed()` |

### 6.5 Guarded Action Path

Every sensitive write goes through this chain:

```
execute_guarded_action(action_type, payload)
  → DecisionClient.recommend() → confidence check (threshold from DECISION_CONFIDENCE_THRESHOLD)
  → PolicyClient.evaluate_action() → verdict:
       AUTHORIZED+verdict_id → ExecutionClient.execute(idempotent_key, ...)
       REFUSED               → outcomes.refused()
       ESCALATE              → outcomes.escalate()
```

### 6.6 Domain Service Clients (`src/clients/`)

Typed httpx.AsyncClient wrappers with timeouts, graceful degradation, and `internal_headers()` auth. Singletons via `@lru_cache`.

| Client | Methods |
|--------|---------|
| **ContextClient** | `get_snapshot(msisdn)`, `verify_identity(customer_id, answer)`, `get_invoices(customer_id)`, `get_balance(customer_id)` |
| **DecisionClient** | `recommend(action_type, context)` |
| **PolicyClient** | `evaluate_action(context)`, `evaluate_response(session_id, text)` — fail-closed (unreachable → ESCALATE) |
| **ExecutionClient** | `execute(idempotency_key, action_type, session_id, payload, policy_verdict_id)` |
| **RoutingClient** | `resolve_available_advisor(skill_tag)` — always None in pilot |
| **NotificationClient** | `notify(customer_id, template, language, params, channel)` |

### 6.7 MCP Clients (`src/mcp_clients/`)

MCP servers accessed via streamable HTTP using `livekit.agents.llm.mcp.MCPServerHTTP` + `MCPToolset`.

| MCP Server | URL | Tools |
|------------|-----|-------|
| **ai-knowledge-rag** (8201) | `KNOWLEDGE_MCP_URL` | `knowledge_search` |
| **ticketing-glpi** (8202) | `TICKETING_MCP_URL` | `create_ticket`, `get_ticket_status`, `resolve_ticket`, `lookup_tickets` |

### 6.8 Tasks (`src/tasks/`)

Sub-flows (`AgentTask[ReturnType]`) that take over the session temporarily:

| Task | Purpose |
|------|---------|
| **ConsentTask** | Ask for recording consent, persist to DB + audit trail |
| **IdentityVerificationTask** | Step-up: ask last 4 CIN digits, max 3 attempts |
| **PaymentConfirmTask** | Confirm exact payment amount before execution |
| **CallbackScheduleTask** | Offer callback when no human advisor free |
| **SimReplacementTaskGroup** | Multi-step SIM replacement (Phase 7 stub) |

### 6.9 Session State (`src/session/`)

- **`SessionUserData`**: Full mutable session state — `session_id`, `language`, `customer_context`, `identity_verified`, `sentiment_history`, `callback_requested`, `conversation_writer`, idempotency key set.
- **`CustomerContext`**: Immutable snapshot — `customer_id`, `full_name`, `msisdn`, `subscription_type`, `is_vip`, `fraud_suspected`.

Attached to `session.userdata` and flows across agent hand-offs.

### 6.10 Conversation Recording (`src/conversation/`)

**`ConversationWriter`**: Enqueue-and-forget pattern — callers enqueue dicts, a background asyncio task drains to Postgres via `asyncio.to_thread`. Transcripts are PII-masked before write. Records: `CallSession`, `Turn`, `SentimentSample`, `EscalationCase`, `CallbackSchedule`, `ConsentRecord`.

### 6.11 Sentiment (`src/sentiment/`)

**`LexicalSentimentScorer`**: Deterministic keyword matching in fr/ar/en. Returns -1.0 (angry), +0.5 (positive), 0.0 (neutral). After 2+ consecutive negative turns, sets `should_offer_escalation = True` system note for the LLM.

### 6.12 Observability (`src/observability/`)

- **`log_masking.py`**: Global `PiiMaskingFilter` on all root log handlers.
- **`metrics_hook.py`**: Wires `UsageCollector`, captures TTFA (time-to-first-audio) and TTFT (time-to-first-token), exports via OpenTelemetry.

### 6.13 Dependencies (`pyproject.toml`)

```
livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia]==1.6.3
mcp>=1.9,<1.10
pydantic==2.10.4
httpx==0.28.1
structlog==24.4.0
```

Internal monorepo packages: `domain-core`, `persistence`, `audit-trail`, `pii-shield`, `observability-kit`, `service-auth`, `cache`, `object-storage`, `notification-client`, `integration-adapters`.

---

## 7. MCP Servers (`mcp-servers/`)

| Server | Description | Dependencies |
|--------|-------------|--------------|
| **ai-knowledge-rag** (8201) | RAG/FAQ knowledge search. Read-only, low-risk. | `mcp>=1.0.0`, `httpx==0.28.1` |
| **ticketing-glpi** (8202) | GLPI ticket lifecycle (create/status/resolve/lookup). | `persistence`, `mcp>=1.0.0`, `httpx==0.28.1` |
| **messaging-gateway** (8203) | Outbound SMS/WhatsApp via notification-service. | `mcp>=1.0.0`, `httpx==0.28.1` |

---

## 8. Other Apps

### 8.1 Token Service (8107)
Mints short-lived LiveKit access tokens. `POST /token` returns JSON with `accessToken` for browser/mobile callers. Dependencies: `livekit-api>=0.8`.

### 8.2 Business API (8108)
Back-office REST API for supervisor/admin dashboards. Serves KPIs, session history, escalation queue. `GET /admin/kpi`, `GET /admin/sessions`, `GET /admin/escalations`.

### 8.3 Supervisor Dashboard (5173)
React 19 + TypeScript 5.7 + Vite 6 SPA. Components: `EscalationQueue.tsx`, `KpiPanel.tsx`, `SessionInspector.tsx`.

### 8.4 Client Widget (5174)
Embedded browser widget for voice calls via `livekit-client`. React + Vite.

---

## 9. Infrastructure

### 9.1 Docker Compose

- **`infra/docker-compose/docker-compose.yml`**: Core infra — Postgres 16, Redis 7, Qdrant, MinIO, OTEL collector, optional LiveKit server (profile: `self-hosted-livekit`).
- **`infra/docker-compose/docker-compose.apps.yml`**: App tier — all 6 services, token-service, business-api, agent-worker, 3 MCP servers. Build from Dockerfiles, read `.env`.

### 9.2 Makefile Lifecycle Commands

| Command | Action |
|---------|--------|
| `make install` | Install all Python packages (correct order) + Honcho |
| `make dev` | Full local dev: install + infra up + migrate + seed + Honcho |
| `make up` | Docker Compose: start all containers |
| `make down` | Stop all containers |
| `make rebuild` | Stop + rebuild + redeploy all containers |
| `make health` | Probe `/health` on every service |
| `make live-logs` | Follow token-service + agent-worker logs |
| `make test` | Run pytest across 13 targets |

### 9.3 Kubernetes / Helm

Helm chart at `infra/helm/telecom-platform/` with templates for namespace, infra, services, gateway, OTEL, secrets.

### 9.4 CI/CD

GitHub Actions (`.github/workflows/ci.yml`):
1. Lint job: `ruff` + `mypy` across all packages
2. Test job: install all packages, run `pytest` per target
3. Build + push Docker images to `ghcr.io` with commit SHA tag

---

## 10. Configuration (.env)

237 env vars across 25 sections feeding Pydantic `BaseSettings` in every service. Key sections:

| Section | Key Variables |
|---------|---------------|
| Database | `DATABASE_URL`, `POSTGRES_*` |
| LiveKit | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| STT | `DEEPGRAM_API_KEY`, `GLADIA_API_KEY`, `STT_MODEL` |
| TTS | `ELEVEN_API_KEY`, `CARTESIA_API_KEY`, `AZURE_SPEECH_KEY`, `TTS_MODEL` |
| LLM | `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `GROQ_API_KEY`, `LLM_PRIMARY_MODEL` |
| MCP | `KNOWLEDGE_MCP_URL`, `TICKETING_MCP_URL`, `MESSAGING_MCP_URL` |
| Domain URLs | `CONTEXT_SERVICE_URL` through `NOTIFICATION_SERVICE_URL` |
| GLPI | `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` |
| Legacy Adapters | `OCS_ADAPTER_URL`, `BILLING_ADAPTER_URL`, `PAYMENT_ADAPTER_URL` etc. |
| Chaos | `CHAOS_BREAK_STT`, `CHAOS_BREAK_LLM`, `CHAOS_BREAK_TTS` |
| OTEL | `OTEL_EXPORTER_OTLP_ENDPOINT` |

---

## 11. Data Flow — Complete Call Scenario

```
CALLER dials in → LiveKit Cloud → dispatches agent-worker

server.py entrypoint:
  └─ build_agent_session(fr)
       → STT = Deepgram(nova-3)
       → LLM = Google(gemini-3.5-flash) —fallback→ NVIDIA(meta/llama-3.1) —fallback→ Groq(llama-3.1)
       → TTS = ElevenLabs(flash_v2_5) —fallback→ Cartesia(sonic-2)
       → VAD = Silero
       → turn_detection = "stt"
  └─ _prefetch_user_data(msisdn=+216...)
       → GET http://context-service:8101/context/{msisdn}
       → returns CustomerContext (name, subscription, VIP status)
  └─ _open_conversation()
       → ConversationWriter starts background queue drain
  └─ session.start(agent=TriageAgent(fr))

TriageAgent.on_enter():
  └─ ConsentTask → "Cet appel est enregistré. Acceptez-vous ?"
     → caller says "Oui" → persist consent + audit
  └─ Greet → "Bonjour Ahmed, comment puis-je vous aider ?"

LOOP (until hang-up or human transfer):
  └─ caller speaks → VAD detects → Deepgram STT transcribes
  └─ BaseTelecomAgent.on_user_turn_completed():
       → LexicalSentimentScorer scores transcript
       → ConversationWriter.enqueue(turn + sentiment) [off path]
       → if 2+ consecutive negative → inject de-escalation note
  └─ LLM generates reply (may invoke tools):
       READ tools (get_invoice_summary):
         → GET http://context-service:8101/invoices/{customer_id}
         → return data → LLM formats reply → TTS speaks
       WRITE tools (make_payment):
         → guard: ensure_identity_verified() → IdentityVerificationTask
         → guarded_action:
             → POST http://decision-service:8103/decision/recommend
             → POST http://policy-service:8104/policy/evaluate-action
               if AUTHORIZED: POST http://execution-service:8105/execution/execute
             → return outcome to LLM → TTS speaks
       ROUTE tools (route_to_billing):
         → return (BillingAgent, "Je vous transfère à la facturation...")
         → LiveKit switches agent on same session
       ESCALATE tools (escalate_to_manager):
         → return (ManagerAgent, "Je vous mets en relation avec un superviseur...")
         → ManagerAgent tries SIP transfer or schedules callback

CALL ENDS:
  └─ writer.finish_session(duration, disposition, peak_frustration)
  └─ attach_metrics() → usage summary logged via OTEL
```

---

## 12. Resilience & Non-Functional Properties

| Property | Mechanism |
|----------|-----------|
| Provider degradation | `FallbackAdapter` with 2-4 ordered providers per chain |
| Fail-closed policy | Unreachable Policy service → ESCALATE verdict |
| Graceful degradation | All HTTP clients return None/[] on error — never crash the call |
| Off-path DB writes | ConversationWriter enqueue-and-forget; voice path never blocks |
| Chaos engineering | `CHAOS_BREAK_*` toggles inject invalid model IDs |
| Idempotent execution | SHA-256(session_id, action_type) — safe retry |
| PII masking | Global logging filter + transcript masking before DB write |
| Audit trail | Hash-chained ledger for every policy verdict + execution |
| Call recording | MinIO/S3 object storage |
| Observability | OpenTelemetry traces + metrics ⇒ OTEL collector ⇒ backend |

---

## 13. Current Known Issues

| Issue | Status | Root Cause |
|-------|--------|-------------|
| Gemini 400 "deadline too short" | Unresolved | `livekit.plugins.google.llm.LLM` hardcodes 5s gRPC deadline; Google requires ≥10s |
| MCP `http_client` TypeError | Unresolved | MCP versions <1.10 may still lack `http_client` kwarg in `streamablehttp_client()` |
| OpenAI quota exhausted | Open. Skipped via `OPENAI_ENABLED=false` in `.env` | No billing on the API key |
| ElevenLabs key empty | Open. TTS falls through to Cartesia | No key available for the account |
| OTEL collector not running | Non-blocking | Container not started; traces silently dropped |
| STT/VAD sync drift | Minor known quirk | LiveKit's STT-based turn detection has edge cases |
| `turn_detection`/`preemptive_generation`/`metrics_collected` deprecation warnings | Non-breaking in v1.6.3 | Will break when upgrading to LiveKit Agents v2.0 |

---

## 14. Key Architectural Rules (from README)

1. **DDD + Clean Architecture**: domain in `packages/domain-core`, services as thin FastAPI wrappers, adapters behind ports.
2. **Zero business logic in agent-worker**: Think "Lego bricks" — tools delegate to service clients.
3. **Vendor boundary**: No `livekit.plugins` import outside `apps/agent-worker/src/providers/`.
4. **Composition root**: Only `server.py` wires providers, agents, and hooks.
5. **Twelve-Factor config**: All settings from environment, nothing hardcoded.
6. **Idempotent execution**: Every sensitive action has a deterministic idempotency key.
7. **Opinionated NOT optional**: PII masking, audit trail, sentiment scoring are always on.
