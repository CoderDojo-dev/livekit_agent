# Code Diagnostic Report

**Scope:** Code-level dependency gaps, structural issues, missing dev tooling, and architectural concerns across the Telecom AI Voice Agent Platform.  
**Excludes:** CLI-specific errors (shell syntax, wrong directory, venv activation from subdirectory) — see STARTUP_DIAGNOSTIC.md for those.

---

## 1. WHY YOU MUST RUN 14+ SEPARATE COMMANDS

**The platform has NO unified startup mechanism.** There is no single command, script, Makefile, or orchestrator to bring everything up. You must manually start:

1. **7 infrastructure containers** (docker compose up — this IS one command, so fine)
2. **7 domain services** (context, knowledge, decision, policy, execution, notification, token) — each a separate uvicorn terminal
3. **1 business API** (business-api) — separate uvicorn terminal
4. **3 MCP servers** (ai-knowledge-rag, ticketing-glpi, messaging-gateway) — 3 separate `python -m` terminals
5. **1 agent-worker** — separate `python src/server.py start` terminal
6. **2 frontends** (supervisor-dashboard, client-widget) — 2 separate `npm run dev` terminals

**That's 20+ terminal windows.**

### Root causes:

**A. No Makefile / task runner**
No `Makefile`, no `justfile`, no `task.py`, no `Procfile`. There is no mechanism to start or group processes.

**B. No process manager integration**
No `procfile`, no `foreman`/`honcho`/`overmind`, no Python `multiprocessing` or `subprocess` launcher. Every component expects to be started manually.

**C. No Docker Compose service definitions for app components**
`infra/docker-compose/docker-compose.yml` defines infrastructure only (postgres, redis, qdrant, minio, livekit, otel, nginx). None of the 8 service apps, 3 MCP servers, agent-worker, or frontends are defined as compose services. Each app container must be built and started individually.

**D. No Python entry-point scripts (`[project.scripts]`)**
Every `pyproject.toml` across all packages, services, and apps lacks a `[project.scripts]` section. For example, instead of running `uvicorn business_api.main:app --port 8108`, a simple `business-api` CLI command could exist. Compare:

| What exists | What should exist |
|---|---|
| `uvicorn context_service.main:app --host 0.0.0.0 --port 8101` | `[project.scripts]` → `context-api = "context_service.main:app"` → `uvicorn context-api --port 8101` |
| `python -m ticketing_glpi.server` | `[project.scripts]` → `ticketing-glpi = "ticketing_glpi.server:main"` |

**E. No intent/order metadata**
There is no documentation of which service depends on which other service, for startup ordering. For example: agent-worker depends on context-service being alive, and context-service depends on postgres being alive. This is not codified anywhere.

---

## 2. DEPENDENCY DECLARATION GAPS (Import-Without-Declare)

Each service imports modules that are NOT listed as direct dependencies in its `pyproject.toml`. The imports resolve only because the module comes **transitively** through another declared dependency (usually `persistence` → `sqlalchemy`). If `pip install` of the transitive provider hasn't been run first, the import fails.

### 2.1 — sqlalchemy (direct import, transitive-only declaration)

**Affected:** 6 components, 11 files.

| File | Import (example) | Declared? |
|---|---|---|
| `services/context-service/src/context_service/main.py:11` | `from sqlalchemy.orm import Session` | **NO** (comes via `persistence`) |
| `services/context-service/src/context_service/repositories.py:8-9` | `from sqlalchemy import select; from sqlalchemy.orm import Session` | **NO** |
| `services/policy-service/src/policy_service/main.py:7` | `from sqlalchemy.orm import Session` | **NO** |
| `services/policy-service/src/policy_service/service.py:10` | `from sqlalchemy.orm import Session` | **NO** |
| `services/execution-service/src/execution_service/main.py:7` | `from sqlalchemy.orm import Session` | **NO** |
| `services/execution-service/src/execution_service/service.py:12-14` | `from sqlalchemy import select; from sqlalchemy.exc import IntegrityError; from sqlalchemy.orm import Session` | **NO** |
| `services/execution-service/src/execution_service/projections.py:14-15` | `from sqlalchemy import select; from sqlalchemy.orm import Session` | **NO** |
| `apps/business-api/src/business_api/main.py:12` | `from sqlalchemy.orm import Session` | **NO** |
| `apps/business-api/src/business_api/repositories.py:4-5` | `from sqlalchemy import func, select; from sqlalchemy.orm import Session` | **NO** |
| `apps/business-api/src/business_api/jobs/integrity.py:10-11` | `from sqlalchemy import func, select; from sqlalchemy.orm import Session` | **NO** |
| `apps/business-api/src/business_api/jobs/retention.py:12-13` | `from sqlalchemy import select, update; from sqlalchemy.orm import Session` | **NO** |

All 11 files directly import `sqlalchemy` classes. All 11 rely on the transitive dependency through `persistence`. None of the 6 `pyproject.toml` files list `sqlalchemy` explicitly.

**Fix:** Either add `"sqlalchemy>=2.0,<2.1"` to each service's dependencies, or refactor all 11 files to import sqlalchemy classes ONLY through `persistence` re-exports.

### 2.2 — httpx (transitive-only in packages)

| File | Import | Declared? |
|---|---|---|
| `packages/notification-client/src/notification_client/client.py:11` | `import httpx` | **NO** (deps only `domain-core`) |
| `services/knowledge-service/src/knowledge_service/retriever.py:78` | `import httpx` (inline in `_openai_embedder()`) | **NO** (deps: qdrant-client, service-auth, fastapi, uvicorn, domain-core) |

Both files import `httpx` but it is not in their `pyproject.toml` dependencies.

**Fix:** Add `"httpx==0.28.1"` to notification-client and knowledge-service dependencies.

### 2.3 — pii-shield (transitive-only for notification-service)

| File | Import | Declared? |
|---|---|---|
| `services/notification-service/src/notification_service/channels.py:16` | `from pii_shield import PiiMasker` | **YES** (listed in notification-service pyproject.toml) |

This one is fine. Verified.

---

## 3. DUPLICATE IMPORTS (Same import on adjacent lines)

4 files contain the exact same import statement on two consecutive lines. While not causing runtime failures (Python deduplicates imports), these are dead lines that survived refactoring:

| File | Lines | Duplicate |
|---|---|---|
| `services/context-service/src/context_service/main.py` | 8–9 | `from fastapi import Depends` ×2 |
| `services/policy-service/src/policy_service/main.py` | 4–5 | `from fastapi import Depends` ×2 |
| `services/execution-service/src/execution_service/main.py` | 4–5 | `from fastapi import Depends` ×2 |
| `services/decision-service/src/decision_service/main.py` | 4–5 | `from fastapi import Depends` ×2 |

The first `from fastapi import Depends, FastAPI` on line 4/8 already imports `Depends`. Line 5/9 is a dead duplicate.

---

## 4. TICKETING-GLPI MCP — Hidden transitive dependency chain

The MCP server `ticketing-glpi` declares `persistence` in `pyproject.toml:7`. However:

**`mirror.py` directly imports `sqlalchemy`:**
- `mirror.py:13` — `from sqlalchemy import select`
- `mirror.py:35-37` — inline imports: `from persistence.engine import session_scope`, `from persistence.models.ticketing import Ticket`, `from persistence.util import to_uuid`

The inline imports inside function bodies (`mirror_create`, `mirror_resolve`, etc.) are used as lazy imports guarded by `_enabled()` — but `sqlalchemy` at module level (line 13) is loaded eagerly. If `persistence` wasn't installed, `mirror.py` fails at import time, not at call time.

**`glpi_ticket_ops.py` uses persistence lazily:**
- `glpi_ticket_ops.py:33` — `await asyncio.to_thread(mirror.mirror_create, ...)` — works because mirror module is already loaded

**`glpi_client.py` uses httpx:**
- `glpi_client.py:74` — `import httpx` is declared ✓

---

## 5. DEAD/ORPHANED CODE PATHS

### 5.1 — Knowledge-service dual retriever leak

`services/knowledge-service/src/knowledge_service/retriever.py` has two implementations:

- `LexicalRetriever` (lines 33–52): Works offline, no deps, deterministic TF-based scoring
- `QdrantRetriever` (lines 58–72): Needs Qdrant client + OpenAI embeddings API

The factory function `get_retriever()` at line 94 gates the Qdrant path on `QDRANT_URL` being set. However, the `qdrant-client` package is a **mandatory dependency** in `pyproject.toml` (declared twice at lines 7 and 8: `"qdrant-client"` and `"qdrant-client==1.12.1"`), meaning you MUST install it even when not using Qdrant. The lexical retriever path exists as a graceful fallback but the dep is still required.

### 5.2 — LiveKit self-hosted server unused when on LiveKit Cloud

`infra/docker-compose/docker-compose.yml:3-13` defines a `livekit-server` container with `LIVEKIT_KEYS: "${LIVEKIT_API_KEY:-devkey}: ${LIVEKIT_API_SECRET:-devsecret_change_me}"`. But the user's `.env` points to LiveKit Cloud (`wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud`) with cloud credentials. The self-hosted livekit-server in compose is **never used** when on LiveKit Cloud, but still starts and consumes memory. The docker compose has no way to opt-out of livekit-server.

---

## 6. ENVIRONMENT VARIABLE REPLICATION PATTERN

Many env vars are repeated across files in the `.env` without a clear single-source-of-truth. There are now TWO `.env` templates:

- `C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\.env.example` (root)
- `C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\deploy\secrets\.env.example` (deploy)

The root `.env.example` has 92 vars (updated). The `deploy/secrets/.env.example` has fewer (about 30) and uses OLD variable names (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `GLPI_ADAPTER_URL` instead of `GLPI_BASE_URL`/`GLPI_APP_TOKEN`/`GLPI_USER_TOKEN`, `POSTGRES_DSN` instead of `DATABASE_URL`). These two files are **out of sync**.

The old state of `deploy/secrets/.env.example` references deprecated variable names that no code reads.

---

## 7. ORDER-OF-INSTALLATION REQUIREMENT (Implicit / Undocumented)

Every service and app depends on shared packages being `pip install`ed first. The dependency chain is:

```
Step 1: pip install ./packages/domain-core  (zero deps)
Step 2: pip install ./packages/persistence  (depends on domain-core via models)
Step 3: pip install ./packages/audit-trail  (depends on persistence)
Step 4: pip install ./packages/service-auth
Step 5: pip install ./packages/cache
Step 6: pip install ./packages/object-storage
Step 7: pip install ./packages/pii-shield
Step 8: pip install ./packages/observability-kit
Step 9: pip install ./packages/notification-client
Step 10: pip install ./packages/integration-adapters
Step 11: pip install ./apps/token-service
Step 12: pip install ./apps/business-api
Step 13: pip install ./apps/agent-worker
Step 14–20: pip install ./services/{each-service}
Step 21–23: pip install ./mcp-servers/{each-mcp}
```

This order is NEVER documented. If you try to run a service before its transitive dependencies are installed (e.g., running `uvicorn policy_service.main:app` before `pip install ./packages/service-auth`), you get `ModuleNotFoundError`. The user hit this twice during startup attempts.

**The `pip install` loop command provided earlier installs ALL shared packages in one shot:**
```bash
pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
    ./packages/pii-shield ./packages/observability-kit ./packages/service-auth \
    ./packages/cache ./packages/object-storage ./packages/notification-client \
    ./packages/integration-adapters
```
But this is not obvious to a first-time user — they would naturally try `uvicorn business_api.main:app` first and hit the sqlalchemy import error.

---

## 8. MISSING `[project.scripts]` IN ALL pyproject.toml FILES

**24 pyproject.toml files** across the project. **0** contain a `[project.scripts]` section. This means:

- No `pip install` + then call a short CLI name workflow
- Every service requires the full `uvicorn package.module:app --host 0.0.0.0 --port XXXX` incantation
- Every MCP requires `python -m ticketing_glpi.server`
- The agent-worker requires `python src/server.py start`

**What each pyproject.toml SHOULD have (example for context-service):**
```toml
[project.scripts]
context-api = "context_service.main:app"
```
Then `uvicorn context-api --port 8101` works after `pip install ./services/context-service`.

---

## 9. NO DEV-IN-A-BOX (Missing integration test / smoke test script)

There is no script that:
1. Checks all infra containers are healthy
2. Checks all services respond on `/health`
3. Checks a minimal end-to-end call flow (token-service → agent-worker → decision → execution)

This means the user must manually verify each of the 20+ processes. If one fails silently (e.g., a service starts but can't connect to Postgres), there is no alert.

---

## 10. SUMMARY TABLE

| # | Category | Severity | Components affected | Impact |
|---|---|---|---|---|
| 1 | No unified startup | **HIGH** | ALL | 20+ terminal windows to start the platform |
| 2 | No `[project.scripts]` | **HIGH** | 24 pyproject.toml files | Every service needs the full uvicorn incantation |
| 3 | sqlalchemy transitive-only (11 files) | **MEDIUM** | context, policy, execution, business-api (6 components) | `ModuleNotFoundError` if persistence not installed first |
| 4 | httpx undeclared (2 files) | **MEDIUM** | notification-client, knowledge-service | `ModuleNotFoundError` if httpx not installed separately |
| 5 | Duplicate imports (4 files) | **LOW** | context, policy, execution, decision main.py | Dead code lines, no runtime effect |
| 6 | Dual .env.example desync | **MEDIUM** | 2 .env.example files | deploy/secrets has deprecated var names |
| 7 | No documented install order | **HIGH** | ALL new users | User hits ModuleNotFoundError repeatedly |
| 8 | No Docker Compose app definitions | **MEDIUM** | All services/workers | Cannot docker compose up the whole platform |
| 9 | LiveKit self-hosted unused on Cloud | **LOW** | docker-compose.yml | Wasted container when on LiveKit Cloud |
| 10 | Knowledge-service mandatory qdrant dep | **LOW** | knowledge-service retriever.py | Lexical fallback exists but qdrant-client still required |
| 11 | No health/smoke script | **MEDIUM** | ALL | Manual verification of 20+ processes on each start |

**Total distinct code-level issues identified:** 11  
**Files requiring attention:** 27