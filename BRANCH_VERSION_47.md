# version_47 — Comprehensive Ruff/MyPy Cleanup + OCS-Billing Simulator + Adapter Hardening

## What Changed

### CI Workflow Hardened
- **`.github/workflows/ci.yml`**: `ruff check .` and `mypy` no longer have `|| true` — they now **fail on errors** instead of silently passing. Every lint/type issue in the codebase was fixed in this version to make CI green.

### Comprehensive Linting/Type Cleanup (67 files)
Across the entire codebase (apps, services, packages, scripts, tests):

- **Import ordering** fixed (ruff I001 rule): stdlib → third-party → local
- **`setattr(obj, attr, val)` → `obj.attr = val`** on `SimpleNamespace` and dataclass objects in resilience monitor and tests
- **`object` → `Any`** in type annotations throughout telemetry, resilience, and knowledge modules
- **`zip(a, b)` → `zip(a, b, strict=False)`** in retriever and reranker
- **`raise HTTPException(...)` → `raise HTTPException(...) from exc`** — proper exception chaining in knowledge-service main.py
- **`FastAPI File` import conflict resolved**: `File` renamed to `FastAPIFile` to avoid shadowing `builtins.File` (ruff F811)
- **Inline module imports** (e.g., `from qdrant_client.models import SparseVector`) moved to top of function blocks per ruff I001
- **Unused imports removed** (e.g., `from frontend_events import FrontendEventPublisher` in server.py, `from datetime import datetime` moved below dataclass import in session_state.py)
- **`FieldCondition` type: ignore comment** added in retriever.py for MatchAny/Filter compatibility

### New Container: `ocs-billing-sim`
- **`services/ocs-billing-sim/`** — new OCS/billing simulator service (Postgres-backed ledger)
  - `ledger.py`: OCS ledger with balance/consumption queries
  - `main.py`: FastAPI server with `/balance` and `/consume` endpoints
  - `Dockerfile` + `pyproject.toml` for container build
- **`docker-compose.apps.yml`**:
  - New `ocs-billing-sim` service (builds from `services/ocs-billing-sim/Dockerfile`, port **8109:8107**, depends on postgres)
  - `execution-service` now depends on `ocs-billing-sim: { condition: service_started }`
- **`.env.example`**: OCS and Billing adapter URLs now default to `http://ocs-billing-sim:8107`

### Adapter Factory Hardening (Live-Only, No Silent Mock)
- **`integration-adapters/factory.py`**: `_pick()` now raises `AdapterConfigError` when `CONNECTOR_MODE=live` but the adapter's URL is not set:
  > _"CONNECTOR_MODE=live but OCS_ADAPTER_URL is not set. Refusing to fall back to the mock 'ocs' adapter, which would fake a real operation."_
- **No more silent mock fallback for money operations** (billing, OCS, payment). Mock is reachable **only** when `CONNECTOR_MODE=mock` is explicitly selected (local dev / CI).
- Tests updated (`test_adapters.py`) for the new live-only behavior.

## Container / SDK Changes
- **New `ocs-billing-sim` container** (Postgres-backed OCS/billing simulator)
- **`execution-service`** now depends on `ocs-billing-sim`
- **No LiveKit SDK version changes**

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `services/ocs-billing-sim/Dockerfile` | NEW | OCS/billing simulator container |
| `services/ocs-billing-sim/pyproject.toml` | NEW | OCS simulator project config |
| `services/ocs-billing-sim/src/ocs_billing_sim/__init__.py` | NEW | Package init |
| `services/ocs-billing-sim/src/ocs_billing_sim/ledger.py` | NEW | OCS ledger implementation |
| `services/ocs-billing-sim/src/ocs_billing_sim/main.py` | NEW | FastAPI server for OCS sim |
| `infra/docker-compose/docker-compose.apps.yml` | MODIFIED | Added ocs-billing-sim service; execution-service depends on it |
| `.env.example` | MODIFIED | OCS/Billing URLs default to ocs-billing-sim:8107 |
| `packages/integration-adapters/src/integration_adapters/factory.py` | MODIFIED | AdapterConfigError: live mode raises on missing URL |
| `packages/integration-adapters/tests/test_adapters.py` | MODIFIED | Tests for live-only adapter behavior |
| `.github/workflows/ci.yml` | MODIFIED | ruff/mypy now fail on errors |
| `apps/agent-worker/src/providers/_resilience.py` | MODIFIED | setattr → direct attr; types cleanup |
| `apps/agent-worker/tests/resilience/test_chaos_wiring.py` | MODIFIED | setattr → direct attr in assertions |
| `services/knowledge-service/src/knowledge_service/main.py` | MODIFIED | File import fix; exception chaining |
| `services/knowledge-service/src/knowledge_service/retriever.py` | MODIFIED | Import ordering; strict=False on zip |
| `packages/observability-kit/src/observability_kit/telemetry.py` | MODIFIED | object → Any in type annotations |
| `apps/agent-worker/src/server.py` | MODIFIED | Import ordering |
| `apps/agent-worker/src/session/session_state.py` | MODIFIED | Import ordering |
| ... and ~50 more files | MODIFIED | Import ordering, unused imports, typing fixes |
