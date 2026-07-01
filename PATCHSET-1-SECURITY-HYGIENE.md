# Patch-Set 1 — Security hardening + code hygiene (tester report)

First batch, grouped by theme. Addresses the 🔴 security items + the quick 🟡 hygiene items + the
`.env` placeholders you asked for. Everything is verified offline; the internal-auth is **opt-in**
so nothing breaks in dev/CI.

## Report items closed (11)
| # | Item | What changed |
|---|---|---|
| 15 🔴 | CORS wide open | `token-service` + `business-api` now read `CORS_ORIGINS` (env allow-list); business-api also **gains CORS** (the dashboard needs it) while keeping RBAC |
| 16 🔴 | Default credentials | `infra/.../docker-compose.yml` now uses `${POSTGRES_*}`, `${MINIO_*}`, `${LIVEKIT_*}` (defaults kept for dev); real values live in `.env` |
| 17 🔴 | No service-to-service auth | new **`packages/service-auth`**: `require_internal_key` (FastAPI dep) on the **6 internal services**, `internal_headers()` on the **5 worker clients**. Opt-in via `INTERNAL_API_KEY` (unset = no-op, so dev/tests are unaffected); `/health` always open |
| 21 🟡 | Docker healthchecks | added to postgres, redis, qdrant, minio in the infra compose |
| 13 🟡 | Connection pool config | `engine.py` now honors `DB_POOL_SIZE/MAX_OVERFLOW/POOL_TIMEOUT/POOL_RECYCLE` |
| 9 🟠 | AccountServicesAgent stub | rewritten on `BaseTelecomAgent` with real tools (plan details / change / recharge / roaming) — all state changes flow through the guarded path |
| 27 🟡 | Wrong base class | same fix (was `Agent`, now `BaseTelecomAgent` → inherits sentiment/de-escalation/logging) |
| 24 🟡 | Build artifacts in repo | `.gitignore` now excludes `*.zip`, `*.egg-info/`, `build/`, `*.egg` |
| 25 🟡 | No mypy config | root `pyproject.toml` `[tool.mypy]` |
| 26 🟡 | No ruff config | root `pyproject.toml` `[tool.ruff]` (+ isort first-party map) |
| — | **.env placeholders** | new **`.env.example`** with every API/link/connector/secret placeholder (GLPI, Twilio/SendGrid/SMTP, OCS/Billing/Payment/CRM/NMS URLs, Qdrant, Redis, MinIO, provider keys, INTERNAL_API_KEY, CORS) — `⚠` marks what a live deploy must set |

## Already fixed (report used an older snapshot)
- **#12 dead code** (`mock_directory.py` / `aggregator.py` / `test_aggregator.py`) — removed back in
  Persistence P1; the context tests already run against pure mapping helpers.
- **#31 dead chaos test** — `LANGUAGE_PRESETS["ar"]["deepgram_language"]` **exists**; the resilience
  suite passes (4/4). No change needed.

## New tools
- `packages/service-auth` — `require_internal_key` (dep) + `internal_headers()` (client) + tests.
- `apps/agent-worker/src/tools/account_tools.py` — `get_plan_details`, `change_plan`, `top_up`,
  `toggle_roaming` (the three writes go through Decision→Policy→Execution).

## Verification
- `service-auth` tests **3**; worker suites **14**; regression: policy 10 · execution 5 · context 4 ·
  notification 6 · business-api 7 — all green. All internal services import with the auth dependency;
  business-api has CORS + its 10 endpoints; the root `pyproject.toml` tool config parses.
- **Auth is safe-by-default**: with `INTERNAL_API_KEY` unset (dev/CI) it's a no-op; set it in every
  internal service + the worker for staging/prod.

## Turn on the hardening (staging)
```bash
export INTERNAL_API_KEY="$(openssl rand -hex 32)"    # same value for the 6 internal services + worker
export CORS_ORIGINS="https://widget.telecom.tn,https://dashboard.telecom.tn"
export POSTGRES_PASSWORD=... MINIO_ROOT_PASSWORD=... LIVEKIT_API_SECRET=...
```

## Coming next (grouped, in order)
- **Patch-Set 2 — Persistence completeness**: OSS (#1) + Provisioning (#2) models + migration 0007;
  GIN indexes (#14) migration 0008; migration tests (#29); patches-dir typo (#28).
- **Patch-Set 3 — Real adapters (behind `CONNECTOR_MODE`)**: integration-adapters (#3), GLPI REST
  client (#4), SMS/WhatsApp/Email channels (#5), execution dispatch via adapters (#10),
  notification-client (#11), messaging-gateway MCP (#2-mcp).
- **Patch-Set 4 — Infra/storage & ops**: Qdrant (#6), Redis (#7), MinIO (#8), Dockerfiles (#30),
  API gateway (#18), CI/CD (#19), Helm (#20), DB backup (#22), secrets (#23).
