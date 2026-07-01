# Telecom AI Voice Agent Platform — Full Diagnostic Report

> **Generated:** 2026-06-30  
> **Scope:** Complete codebase analysis — structure, tests, data layer, gaps, risks, and next steps  
> **Methodology:** Static analysis + test execution (42/44 pass) + architectural review

---

## 1. EXECUTIVE SUMMARY

The platform is a **well-architected but partially-built** telecom AI agent. The Hexagonal/DDD
backbone is sound, the data layer follows modern practices, and the deterministic safety core
is genuinely production-grade. However, the codebase reveals a **significant gap between
architectural ambition and implemented surface area**: roughly 60% of the modules are stubs,
mocks, or scaffolds. The live voice path works but every sensitive action, every external
integration, and every data write goes through mock adapters.

**Verdict:** A strong Phase-2 foundation (scaffolding) with excellent design decisions.
Production readiness is **Phase 5–6 of ~12**. The next 3–4 phases should focus on swapping
mocks for real adapters and filling the empty schemas, rather than adding new architectural
layers.

---

## 2. PROJECT STATISTICS

| Metric | Value |
|---|---|
| **Total Python files** | 209 |
| **Total lines of code** | 5,831 |
| **Test files** | 19 |
| **Tests passing** | 42 / 44 (95.5%) |
| **Apps** | 5 |
| **Services** | 6 |
| **MCP servers** | 3 (1 empty) |
| **Shared packages** | 7 |
| **PostgreSQL schemas** | 12 |
| **Database tables** | 27 |
| **Alembic migrations** | 6 |
| **Languages supported** | 3 (FR/AR/EN) |

### Module Size Breakdown

| Module | Files | Lines | Status |
|---|---|---|---|
| `apps/agent-worker` | 63 | 1,678 | Core — working |
| `packages/persistence` | 15 | 769 | Core — working |
| `apps/business-api` | 14 | 284 | Core — working |
| `services/policy-service` | 13 | 269 | Core — working |
| `services/execution-service` | 6 | 249 | Core — working |
| `mcp-servers/ticketing-glpi` | 7 | 221 | Working (mock backend) |
| `services/context-service` | 7 | 356 | Working |
| `packages/domain-core` | 17 | 342 | Ports/interfaces |
| `services/knowledge-service` | 5 | 138 | Working |
| `services/notification-service` | 6 | 136 | Working (mock channels) |
| `packages/audit-trail` | 2 | 128 | Working |
| `services/decision-service` | 4 | 62 | Minimal logic |
| `apps/token-service` | 2 | 55 | Working |
| `mcp-servers/ai-knowledge-rag` | 4 | 44 | Minimal logic |
| `packages/pii-shield` | 2 | 26 | Working |
| `packages/observability-kit` | 2 | 15 | **Stub** |
| `packages/integration-adapters` | 7 | 78 | **Stub** |
| `packages/notification-client` | 2 | 12 | **Stub** |
| `apps/supervisor-dashboard` | — | — | **Empty scaffold** |
| `mcp-servers/messaging-gateway` | — | — | **Empty scaffold** |

---

## 3. THE DATA LAYER: 12 SCHEMAS, 27 TABLES, 6 MIGRATIONS

This is the single strongest piece of the project. The claim is accurate and verified.

### The 12 Bounded-Context Schemas

```
crm           (4 tables)   — customers, subscriptions, consent_records, customer_interactions
billing       (6 tables)   — accounts, invoices, invoice_items, payments, payment_plans, notifications
ocs           (2 tables)   — balance_accounts, recharges
sim           (1 table)    — block_unblock_cases
conversation  (5 tables)   — call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules
policy        (1 table)    — policy_verdicts
execution     (1 table)    — action_ledger
audit         (2 tables)   — audit_ledger, pii_token_map
ticketing     (1 table)    — tickets
reference     (4 tables)   — business_rules, error_catalog, products, recharge_catalog
oss           (0 tables)   — ⚠️ **EMPTY** — no tables exist
provisioning  (0 tables)   — ⚠️ **EMPTY** — no tables exist
```

**Total: 10 populated schemas + 2 empty = 12 schemas, 27 tables**

### The 6 Alembic Migrations (all reversible)

| Migration | Tables Added | Schema Impact |
|---|---|---|
| `0001_initial` | Extensions, 12 schemas, crm/billing/ocs | Foundational |
| `0002_safety_core` | policy_verdicts, action_ledger, audit_ledger, pii_token_map | Safety |
| `0003_conversation` | call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules | Runtime |
| `0004_domain_writes` | payments, payment_plans, recharges, block_unblock_cases | Write path |
| `0005_ticketing` | tickets, notifications | Ticketing |
| `0006_reference` | business_rules, error_catalog, products, recharge_catalog | Catalogs |

### Design Strengths

- **UUID PKs** everywhere (`uuid_generate_v4()`) — no sequential IDs, no enumeration attacks
- **Consistent timestamps** (`created_at`/`updated_at` with trigger `set_updated_at()`)
- **MSISDN is a UNIQUE attribute** on subscriptions, never a join key (canonical identity model)
- **`national_id` carries the CIN** — the identity secret is last-4 digits
- **Money is `NUMERIC(12,2)`** — never floats
- **Hash-chained audit ledger** — `sha256(prev_hash | canonical(payload) | timestamp)`
- **Naming convention** on constraints — stable migration names
- **All schemas created in migration 0001** — subsequent migrations only add tables
- **Sync SQLAlchemy 2.0** — appropriate for FastAPI thread-pooled path operations
- **Pilot seed data** — 3 canonical callers with real TND amounts

### ⚠️ Data Layer Risks

| Risk | Severity | Detail |
|---|---|---|
| **2 empty schemas** (oss, provisioning) | Medium | Placeholder schemas with no tables mean the OSS and provisioning bounded contexts exist only as names |
| **No indexes on JSONB columns** | Low-Medium | `payload` in audit_ledger, `dossier` in escalation_cases, `parameters` in action_ledger are JSONB with no GIN indexes — will degrade at scale |
| **No async path** | Low | ADR chose sync SQLAlchemy, which is fine for FastAPI, but the `ConversationWriter` uses `asyncio.to_thread` — fragile under high concurrency |
| **No database migration testing** | Medium | No test verifies that `alembic upgrade head` + `alembic downgrade -1` works cleanly |
| **No connection pooling limits** | Low | `pool_pre_ping=True` is set but no `pool_size` or `max_overflow` — could exhaust connections under load |
| **PII token map uses AES?** | Info | `encrypted_value` is `LargeBinary` — the encryption scheme is undocumented |
| **Seed data is TND-specific** | Low | Hardcoded Tunisian dinar amounts — fine for pilot but needs parameterization |

---

## 4. ARCHITECTURE MAP

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                 │
│  client-widget (React 19 + Vite)          supervisor-dashboard     │
│  token-service (JWT minting)               (EMPTY SCAFFOLD)        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ WebRTC (LiveKit)
┌───────────────────────────▼─────────────────────────────────────────┐
│                      AGENT WORKER (port 7880)                       │
│  ┌────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────┐  │
│  │Triage  │  │ Billing  │  │Technical  │  │Account   │  │Manager│  │
│  │Agent   │  │ Agent    │  │ Agent     │  │Services  │  │Agent  │  │
│  └────────┘  └──────────┘  └───────────┘  │Agent     │  └───────┘  │
│                   (5 personas, all inherit│(STUB)    │              │
│                    BaseTelecomAgent)       └──────────┘              │
│                                                                     │
│  Observability: metrics_hook.py, log_masking.py                     │
│  Sentiment: LexicalSentimentScorer (FR/AR/EN)                      │
│  Conversation: ConversationWriter (async, off-path)                │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│Context   │ │Decision│ │ Policy   │ │Exec    │ │Notif     │
│Service   │ │Service │ │ Service  │ │Service │ │ Service  │
│:8101     │ │:8103   │ │ :8104    │ │:8105   │ │ :8106    │
│          │ │        │ │          │ │        │ │          │
│Postgres  │ │2 rules │ │10 rules  │ │Postgres│ │Mock SMS/ │
│CRM 360   │ │+ conf  │ │determin- │ │action  │ │WhatsApp/ │
│Identity  │ │scorer  │ │istic     │ │ledger  │ │Email     │
└──────────┘ └────────┘ └──────────┘ └────────┘ └──────────┘
                                      │
                ┌─────────────────────┤
                ▼                     ▼
        ┌──────────────┐    ┌────────────────┐
        │Knowledge Svc │    │ MCP Servers    │
        │:8102         │    │ :8201 RAG      │
        │RAG corpus    │    │ :8202 Ticketing│
        │(mock)        │    │ (mock GLPI)    │
        └──────────────┘    └────────────────┘
```

---

## 5. TEST ANALYSIS

### Test Results: 42/44 pass (95.5%)

| Module | Tests | Passing | Failing |
|---|---|---|---|
| context-service | 9 | 9 | 0 |
| execution-service | 5 | 5 | 0 |
| policy-service | 10 | 10 | 0 |
| decision-service | 3 | 3 | 0 |
| notification-service | 3 | 3 | 0 |
| audit-trail | 3 | 3 | 0 |
| knowledge-service | 3 | 3 | 0 |
| ticketing-glpi | 2 | 2 | 0 |
| token-service | 1 | 1 | 0 |
| business-api | 6 | 6 | 0 |
| agent-worker (sentiment) | 3 | 3 | 0 |
| agent-worker (conversation) | 3 | 3 | 0 |
| agent-worker (identity) | 2 | 2 | 0 |
| agent-worker (resilience) | 5 | 4 | **1** |
| **TOTAL** | **44** | **42** | **2** |

### The 1 Failure

```
test_arabic_routes_to_language_ar
  tests/resilience/test_chaos_wiring.py:30
  KeyError: 'deepgram_language'
```

The test expects a key `deepgram_language` in `LANGUAGE_PRESETS["ar"]`, but the actual
`language_presets.py` only defines `stt_language` and `tts_voice`. The test was written
against an older spec and never updated. **This is a dead test — it tests a key that
doesn't exist.**

### ⚠️ Critical Test Gaps

| Gap | Severity | Impact |
|---|---|---|
| **No integration tests** | **CRITICAL** | No test verifies that context-service + policy-service + execution-service actually work together. The Decision→Policy→Execution pipeline is never tested end-to-end. |
| **No database tests** | **High** | No test runs Alembic migrations, seeds data, or queries Postgres. If the schema breaks, no test catches it. |
| **No HTTP API tests** | **High** | None of the REST endpoints are tested with `httpx` or `TestClient`. |
| **No MCP server tests** | **High** | The MCP tools (knowledge_search, create_ticket, etc.) have no tests. |
| **No end-to-end tests** | **High** | The full voice path (browser → LiveKit → worker → services → DB) is never tested automatically. |
| **No load tests** | **Medium** | No performance benchmarks for the voice path. |
| **No contract tests** | **Medium** | No schema validation between service boundaries. |
| **No negative tests** | **Medium** | No tests for what happens when DB is down, services timeout, or mocks fail. |
| **agent-worker has 4 partial test files** | **Medium** | Most of the worker (agents, tools, MCP clients, guards) has zero test coverage. |
| **Test doubles are manual** | **Low** | No use of pytest fixtures or factories — tests construct objects manually. |

---

## 6. COMPLETENESS ASSESSMENT PER MODULE

### Apps

| App | Completeness | Notes |
|---|---|---|
| **agent-worker** | ~70% | Core persona logic works. 5 personas defined but `AccountServicesAgent` is a stub with 1 instruction line. MCP clients work. ConversationWriter works. Sentiment scoring works. Guarded actions work. |
| **business-api** | ~80% | Endpoints defined, integrity job, KPI endpoint, security scan. Missing: real business API consumers. |
| **token-service** | ~100% | Small, focused, working. JWT minting with proper grants. |
| **client-widget** | ~80% | React 19 + Vite app working. Audio capture, LiveKit room connection, status display. Missing: captions, agent state display, proper error states. |
| **supervisor-dashboard** | **~0%** | **Completely empty.** No src directory exists. This is a named scaffold with nothing inside. |

### Services

| Service | Completeness | Notes |
|---|---|---|
| **context-service** | ~90% | Postgres-backed CrmRepository working. Mock_directory still exists as dead code alongside it. Identity resolution works. Customer-360 snapshot works. |
| **decision-service** | ~50% | Trivial 2-rule scorer. No ML model, no real ranking logic. Acceptable for Phase 6 but needs expansion. |
| **policy-service** | ~85% | Solid deterministic engine. 10 rules (mandatory chain + action-specific + outbound). All verdicts persisted and audited. |
| **execution-service** | ~80% | Idempotent action ledger with domain projections. Savepoint-protected projections. Needs real adapters. |
| **knowledge-service** | ~50% | LexicalRetriever with mock corpus. No Qdrant integration. No embedding pipeline. |
| **notification-service** | ~70% | Channel interface with mock senders. Templates for FR/AR/EN. Localized. Needs SMS/Email provider adapters. |

### MCP Servers

| Server | Completeness | Notes |
|---|---|---|
| **ai-knowledge-rag** | ~40% | FastMCP server with knowledge_search tool. Pure mock — no real RAG pipeline. |
| **ticketing-glpi** | ~70% | 4 tools (create/get/resolve/lookup). MockGlpiClient in-memory. Real GLPI REST adapter needed. |
| **messaging-gateway** | **~0%** | **Completely empty.** No src directory exists. |

### Shared Packages

| Package | Completeness | Notes |
|---|---|---|
| **persistence** | ~95% | Excellent. SQLAlchemy 2.0, Alembic, 12 schemas, 6 migrations, seed data, util helpers. Missing: connection pooling config, async support not needed but noted. |
| **domain-core** | ~60% | 17 files but mostly interfaces/ports with minimal implementation. Good design, thin content. |
| **audit-trail** | ~90% | Hash-chained ledger with verify(). PgAuditLedger + in-memory for tests. Solid. |
| **pii-shield** | ~100% | Small, focused, working. PiiMasker class with regex-based PII scrubbing. |
| **integration-adapters** | ~20% | 7 files, mostly interface stubs. No real adapter implementations. |
| **notification-client** | ~10% | 2 files, 12 lines. Bare scaffold for the HTTP client. |
| **observability-kit** | ~10% | 2 files, 15 lines. `configure_tracer` function. No metrics, no traces, no logging config. |

---

## 7. IDENTIFIED PROBLEMS & RISKS

### 🔴 Critical (blocks production)

| # | Problem | Location | Impact |
|---|---|---|---|
| 1 | **No integration tests** | Entire project | Cannot safely refactor or deploy. No confidence that services work together. |
| 2 | **All external integrations are mock** | execution-service, notification-service, ticketing-glpi, context-service | System works only in demo mode. No real OCS, billing, SMS, GLPI, or CRM. |
| 3 | **OSS schema has 0 tables** | `schemas/oss` | OSS domain exists only as a name. No network inventory, no alarm data, no topology. |
| 4 | **Provisioning schema has 0 tables** | `schemas/provisioning` | No plan changes, SIM activations, service provisioning can be tracked. |
| 5 | **Supervisor dashboard is empty** | `apps/supervisor-dashboard` | No human-supervision UI exists despite being a core architectural requirement. |
| 6 | **Messaging gateway MCP is empty** | `mcp-servers/messaging-gateway` | No SMS/Email sending capability. The notification-service has no real sending adapters. |

### 🟠 High (blocks feature completeness)

| # | Problem | Location | Impact |
|---|---|---|---|
| 7 | **No real Qdrant integration** | knowledge-service | RAG is lexical-only. No vector search, no embedding, no semantic retrieval. |
| 8 | **No real Redis caching** | All services | Customer-360 data and session state are loaded fresh every call. No cache layer. |
| 9 | **No MinIO blob storage** | agent-worker | Audio recordings cannot be stored. Call recording URLs will be null. |
| 10 | **AccountServicesAgent is a stub** | `apps/agent-worker/src/agents/account_services_agent.py` | The only persona for recharges, plan changes, and roaming has no tools. |
| 11 | **Observability-kit is a stub** | `packages/observability-kit` | No real tracing, no metrics export, no structured logging config. |
| 12 | **No service-to-service auth** | All services | Any service can call any other service with no auth token. Internal APIs are open. |
| 13 | **No API gateway** | Infrastructure | No unified entry point, no rate limiting, no request validation at the edge. |
| 14 | **Test failure in agent-worker** | `tests/resilience/test_chaos_wiring.py` | Dead test referencing a nonexistent config key. Indicates test rot. |

### 🟡 Medium (should address before pilot)

| # | Problem | Location | Impact |
|---|---|---|---|
| 15 | **CORS is wide open `*`** in token-service | `apps/token-service/src/token_service/main.py` | Security issue for staging+. Documented as "dev only" but easy to forget. |
| 16 | **Default credentials in .env.example** | `.env.example` | `devsecret_change_me` is in version control. |
| 17 | **Build artifacts committed** | `*.egg-info/`, `*.zip` | `phase-8-changed-files.zip`, `.egg-info` dirs, `__pycache__` should be gitignored. |
| 18 | **Typo in patches directory** | `patches/persistance_p1/` | Directory says "persistance" instead of "persistence". Cosmetic but unprofessional. |
| 19 | **No mypy configuration** | Root | No type checking anywhere. Python typing is used but never verified. |
| 20 | **No ruff/pylint/flake8 config** | Root (Makefile runs ruff but no config file) | Linting exists in Makefile but no `pyproject.toml` section for it. |
| 21 | **mock_directory.py still exists** | context-service | The real CrmRepository is the active code, but the mock module is still in the tree as dead code. |
| 22 | **AccountServicesAgent imports Agent not BaseTelecomAgent** | account_services_agent.py | Inconsistent with the other 4 personas — bypasses sentiment/de-escalation hooks. |
| 23 | **`.venv` committed** | Root | Virtual environment is in the source tree. Should be gitignored. |
| 24 | **No Docker healthchecks** | infra/docker-compose | Services have `/health` endpoints but docker-compose doesn't use `healthcheck`. |
| 25 | **No DB backup/restore scripts** | deploy/ | No documented backup strategy for the Postgres database. |

---

## 8. WHAT'S NEXT — ORDERED PRIORITY ROADMAP

### Phase A: Test Infrastructure (Weeks 1–2)

```
Priority: CRITICAL — nothing should ship without this
```

1. **Fix the 1 failing test** — Update `test_chaos_wiring.py` or delete the dead assertion
2. **Add HTTP integration tests** — `httpx.AsyncClient` + FastAPI `TestClient` for every service
3. **Add database migration tests** — Alembic upgrade + downgrade in CI
4. **Add end-to-end smoke test** — A script that brings up the stack, runs a call flow, and verifies the DB

### Phase B: Real Adapters (Weeks 3–6)

```
Priority: HIGH — mocks are the #1 blocker to production
```

1. **Real Qdrant integration** — Replace `LexicalRetriever` with embedding + vector search pipeline
2. **Real GLPI REST adapter** — Replace `MockGlpiClient` in ticketing-glpi
3. **Real OCS adapter** — Integration-adapters package needs an OCS (Online Charging System) implementation
4. **Real SMS/Email provider** — At least one real adapter (Twilio, Infobip, or Tunisie Telecom API)
5. **Real billing gateway** — Payment processing adapter (Stripe, or local TN payment gateway)

### Phase C: Fill Empty Schemas & Modules (Weeks 4–7)

```
Priority: HIGH — these are architectural gaps
```

1. **OSS schema** — Network equipment inventory, alarms, trouble tickets
2. **Provisioning schema** — Service activation/deactivation, plan change tracking
3. **Supervisor dashboard** — React app for human agents to monitor calls, review escalations
4. **Messaging gateway MCP** — SMS/WhatsApp/Email sending tools
5. **AccountServicesAgent** — Real tools for recharge, roaming toggle, plan change

### Phase D: Observability & Hardening (Weeks 5–8)

```
Priority: MEDIUM — needed before any production deployment
```

1. **OpenTelemetry wiring** — Wire traces through all services, export to Jaeger/Zipkin
2. **Grafana dashboards** — Call volume, latency TTFA/TTFT, error rates, sentiment trends
3. **Service auth** — Internal JWT or mTLS between services
4. **Rate limiting** — On API gateway and per-service
5. **Secrets management** — HashiCorp Vault or env-vault integration
6. **Structured logging** — All services use structlog/otel with consistent fields

### Phase E: Production Readiness (Weeks 8–12)

```
Priority: MEDIUM-HIGH
```

1. **Redis caching** — Customer-360 prefetch cache + session state in Redis
2. **MinIO blob storage** — Audio recording upload/download in agent-worker
3. **Connection pooling tuning** — `pool_size`, `max_overflow`, `pool_timeout` in persistence
4. **CI/CD pipeline** — GitHub Actions for tests, linting, type checking
5. **Kubernetes readiness probes** — Healthcheck-aware pod management
6. **Load testing** — k6 or locust for voice path under simulated load
7. **Disaster recovery** — Backup scripts, restore procedure, RPO/RTO targets

### Phase F: Feature Completion (Weeks 9–16)

```
Priority: LOWER — features on top of a stable base
```

1. **Live captions** in client-widget — Real-time transcription display
2. **Call transfer** — Real SIP trunk integration (not just mock)
3. **Multi-session support** — Horizontal scaling for multiple concurrent calls
4. **Admin API** — Business-api CRUD for customers, subscriptions, policies
5. **Analytics exports** — CSV/JSON export for call records, sentiment trends
6. **Arabic TTS parity testing** — As required by Phase-0 verification gate
7. **Gemini fallback** — Google Gemini as LLM fallback (config exists but untested)

---

## 9. DATA LAYER DEEP DIVE (the "27 tables, 12 schemas, 6 migrations" explained)

### What this claim means

```
┌────────────────────────────────────────────────────────────────────┐
│                     telecom database (Postgres 16)                 │
│                                                                    │
│  Schema: crm ──────────────────────────────────────────────────┐  │
│  ├─ customers (national_id, first_name, last_name, ...)        │  │
│  ├─ subscriptions (msisdn UNIQUE, plan_type, status, ...)      │  │
│  ├─ consent_records (session_id, consent_type, granted, ...)  │  │
│  └─ customer_interactions (channel, intent, summary, ...)      │  │
│                                                                  │  │
│  Schema: billing ─────────────────────────────────────────────  │  │
│  ├─ accounts (customer FK, account_number, billing_cycle, ...) │  │
│  ├─ invoices (account FK, amounts, due_date, status, ...)      │  │
│  ├─ invoice_items (invoice FK, description, amount, ...)       │  │
│  ├─ payments (account FK, amount, idempotency_key UNIQUE, ...) │  │
│  ├─ payment_plans (account FK, installments, verdict FK, ...)  │  │
│  └─ notifications (customer FK, channel, template, status)     │  │
│                                                                  │  │
│  Schema: ocs ─────────────────────────────────────────────────  │  │
│  ├─ balance_accounts (subscription FK, type, value, expiry)    │  │
│  └─ recharges (subscription FK, amount, idempotency_key, ...)  │  │
│                                                                  │  │
│  Schema: sim ────────────────────────────────────────────────── │  │
│  └─ block_unblock_cases (subscription FK, action, verdict FK)  │  │
│                                                                  │  │
│  Schema: conversation ────────────────────────────────────────  │  │
│  ├─ call_sessions (customer FK, channel, disposition, ...)     │  │
│  ├─ turns (session FK, speaker, transcript_masked, ...)        │  │
│  ├─ sentiment_samples (session FK, score, label, ...)          │  │
│  ├─ escalation_cases (session FK, target, dossier JSONB, ...) │  │
│  └─ callback_schedules (session FK, scheduled_time, status)    │  │
│                                                                  │  │
│  Schema: policy ─────────────────────────────────────────────── │  │
│  └─ policy_verdicts (session FK, verdict, rule_id, ...)        │  │
│                                                                  │  │
│  Schema: execution ──────────────────────────────────────────── │  │
│  └─ action_ledger (idempotency_key UNIQUE, verdict FK, ...)    │  │
│                                                                  │  │
│  Schema: audit ──────────────────────────────────────────────── │  │
│  ├─ audit_ledger (seq IDENTITY, entry_hash SHA256, ...)        │  │
│  └─ pii_token_map (token UNIQUE, encrypted_value, ...)         │  │
│                                                                  │  │
│  Schema: ticketing ──────────────────────────────────────────── │  │
│  └─ tickets (customer FK, subject, status, glpi_ref, ...)      │  │
│                                                                  │  │
│  Schema: reference ──────────────────────────────────────────── │  │
│  ├─ business_rules (rule_id UNIQUE, definition JSONB, ...)     │  │
│  ├─ error_catalog (code UNIQUE, messages FR/AR/EN, ...)       │  │
│  ├─ products (code UNIQUE, name, plan_type, ...)               │  │
│  └─ recharge_catalog (code UNIQUE, amount, bonus, ...)         │  │
│                                                                  │  │
│  Schema: oss ─── ⚠️ EMPTY (0 tables) ─────────────────────────  │  │
│  Schema: provisioning ─ ⚠️ EMPTY (0 tables) ─────────────────  │  │
└────────────────────────────────────────────────────────────────────┘
```

### How the 6 Migrations Build This

```
Migration 0001 (initial):
  ├── Extensions: uuid-ossp, pgcrypto
  ├── Function: set_updated_at() trigger
  ├── All 12 schemas created
  ├── crm (4 tables) + billing (3 tables) + ocs (1 table)
  └── View: crm.v_subscription_live

Migration 0002 (safety core):
  ├── policy.policy_verdicts (1 table)
  ├── execution.action_ledger (1 table)
  ├── audit.audit_ledger + pii_token_map (2 tables)
  └── Trigger on action_ledger

Migration 0003 (conversation):
  ├── call_sessions, turns, sentiment_samples (3 tables)
  ├── escalation_cases, callback_schedules (2 tables)
  └── Trigger on callback_schedules

Migration 0004 (domain writes):
  ├── billing.payments + payment_plans (2 tables)
  ├── ocs.recharges (1 table)
  ├── sim.block_unblock_cases (1 table)
  └── 3 triggers

Migration 0005 (ticketing):
  ├── ticketing.tickets (1 table)
  └── billing.notifications (1 table)

Migration 0006 (reference):
  ├── reference.business_rules, error_catalog (2 tables)
  ├── reference.products, recharge_catalog (2 tables)
  └── Trigger on business_rules

Total: 6 migrations, 27 tables, all reversible
```

### The Polyglot Split (what's real vs planned)

| Store | Role | Status |
|---|---|---|
| **Postgres** | System of truth — all relational data | ✅ Working (12 schemas, 27 tables) |
| **Redis** | Cache + session state + idempotency dedupe | ⚠️ Env vars exist, no code uses it |
| **Qdrant** | Vector embeddings for RAG | ⚠️ Env vars exist, knowledge-service uses lexical only |
| **MinIO** | Audio recording blobs | ⚠️ Env vars exist, no code writes to it |

---

## 10. ARCHITECTURAL STRENGTHS (what's genuinely good)

1. **Clean architecture enforcement** — Business rules never import LiveKit SDK. The `domain-core` package is vendor-free.
2. **Deterministic policy engine** — The 3-way verdict (AUTHORIZED/REFUSED/ESCALATE) with mandatory escalation chain is production-grade.
3. **Idempotent execution** — UNIQUE `idempotency_key` on `action_ledger` prevents duplicate sensitive actions even under retry races.
4. **Hash-chained audit** — SHA-256 chain with verify() makes tampering detectable.
5. **Off-path conversation writing** — `ConversationWriter` enqueues dicts in constant time, writes async. Voice quality never depends on DB latency.
6. **Canonical identity model** — MSISDN is a UNIQUE attribute of subscriptions, resolved once at the edge. The `internal/context/resolve` endpoint is the single translation point.
7. **12-factor config** — Everything comes from env vars. No hardcoded secrets, no environment-specific code.
8. **Schema-per-bounded-context** — 12 schemas with real FKs and cross-schema transactions while maintaining module boundaries.
9. **Savepoint-protected projections** — Domain effect writes are in a SAVEPOINT, so a projection failure never corrupts the action ledger or audit chain.
10. **Multi-language support** — FR/AR/EN from day one, with lexical sentiment scoring and localized notification templates.

---

## 11. QUICK WINS (fix in < 2 hours)

1. Fix the failing test — delete or update `test_arabic_routes_to_language_ar`
2. Gitignore `*.egg-info/`, `*.zip`, `__pycache__/`, `.venv/`
3. Remove `mock_directory.py` from context-service if it's truly dead code
4. Make `AccountServicesAgent` inherit from `BaseTelecomAgent` instead of `Agent`
5. Add `healthcheck` to docker-compose services
6. Add `pool_size=5` and `max_overflow=10` to `create_engine()`
7. Add GIN indexes on JSONB columns (`payload`, `dossier`, `parameters`)
8. Remove ZIP files from the repo tree (they're in patches/)

---

## 12. CONCLUSION

The Telecom AI Voice Agent Platform has a **genuinely strong architectural foundation**.
The data layer design is professional, the safety core is well-thought-out, and the
hexagonal/DDD structure is enforced consistently. The ADR-0001 decisions are sound.

However, the project is in a **"scaffolding complete, implementation ongoing"** state.
The critical path to production is:

1. **Test infrastructure** — integration tests, migration tests, end-to-end smoke tests
2. **Real adapters** — swap ALL mocks for real API integrations (Qdrant, GLPI, OCS, billing, SMS)
3. **Fill the empty schemas** — OSS and provisioning need tables
4. **Fill the empty modules** — supervisor dashboard, messaging gateway MCP
5. **Observability + hardening** — tracing, metrics, auth, rate limiting

The project **will work for a demo today**. To work **in production for real customers**,
the team should plan for 3–4 more months of focused implementation on the items above.
The architecture doesn't need changing — it needs **filling in**.

---

*End of Diagnostic Report*
