# Cookbook — P2-5 Verified Fix: Live Adapters Authenticate to the Internal Sims

> **Base:** workspace HEAD after P2-4 (v89 era + P2-4 fixes, alembic head
> `0017_notification_failure_reason`)
> **Scope:** ONE bug, verified against source on 2026-08-15: with `INTERNAL_API_KEY` set (the
> documented posture since P0-1), **every** `CONNECTOR_MODE=live` adapter call to the sims fails
> with 403 — i.e. the whole live execution path is down in the secured stack.
> **Migration:** none. **Dependency change:** one package metadata line (`integration-adapters`
> gains `service-auth`, already installed in every image). **New config:** none.
> **Containers to rebuild after apply:** `execution-service` (only runtime consumer of adapters);
> the other 11 images install the same package but never call it at runtime — they pick up the
> change on their next routine rebuild.

---

## 0. Verification verdict — **CONFIRMED, not a false positive**

Evidence chain (every line read during verification):

1. **The servers enforce the key.** `packages/service-auth/src/service_auth/__init__.py:21-29` —
   `require_internal_key` raises 403 unless `X-API-Key` matches `INTERNAL_API_KEY`; no-op when the
   env var is unset (dev/tests); `/health` always allowed. All three sims apply it **app-wide**:
   - `services/provisioning-sim/src/provisioning_sim/main.py:31` —
     `FastAPI(..., dependencies=[Depends(require_internal_key)])`
   - `services/ocs-billing-sim/src/ocs_billing_sim/main.py:31` — same
   - `services/nms-sim/src/nms_sim/main.py:23` — same
2. **The adapters send nothing.** `packages/integration-adapters/src/integration_adapters/_http.py:9-19`
   — `post_json`/`get_json` build `httpx.AsyncClient(base_url=..., timeout=...)` with **no headers
   parameter at all**. Six adapters ride these helpers: `billing_adapter.py:9`,
   `glpi_adapter.py:9`, `ocs_adapter.py:8`, `nms_adapter.py:7`, `provisioning_adapter.py:14`,
   `payment_adapter.py:6`.
3. **The key is documented as required.** `.env.example:26-30` — "REQUIRED since P0-1... set one
   shared key for every service". The live docker stack sets it, which is exactly when the 403s
   appear (observed during the P2-4 apply at `provisioning-sim:8109/sim/roaming`).
4. **The blast radius is the entire live execution path.**
   `services/execution-service/src/execution_service/executor.py:71-95` — `EXECUTE_PAYMENT`,
   `PAYMENT_DEFERRAL`, `TOP_UP` (→ ocs-billing-sim), `CHANGE_PLAN`, `ACTIVATE_ROAMING`,
   `UNBLOCK_SIM`, `REACTIVATE_SIM`, `REPLACE_SIM` (→ provisioning-sim) all dispatch through these
   adapters. And `integration_adapters/config.py:7-9` — `CONNECTOR_MODE` **defaults to `live`**.
   Combined with the factory's "never silently mock" stance (`factory.py:34-43`), the platform's
   honesty guarantee currently resolves to: *secured stack + defaults = every sensitive action
   fails with 403.* The failure is loud (good), but the feature is dead (bad).
5. **The adapters are the ONLY internal callers that don't authenticate.** All eight agent-worker
   clients (`clients/callback_client.py:15,26`, `context_client.py:16,25`, `decision_client.py:11,20`,
   `execution_client.py:13`, `nms_client.py` (×3), `notification_client.py`, `policy_client.py`,
   `routing_client.py`) import `from service_auth import internal_headers` and pass it to their
   httpx clients. The two MCP servers replicate the same env-read locally
   (`ticketing_glpi/tools/glpi_ticket_ops.py:40-46`, `messaging_gateway/tools/messaging_ops.py:15-16`)
   because their packages don't depend on `service-auth`. The adapters do neither — an oversight,
   not a design.
6. **The dependency is already paid for.** `services/execution-service/Dockerfile:8` installs
   `./packages/service-auth` in the same layer as `./packages/integration-adapters`;
   `services/execution-service/pyproject.toml:9` already declares `service-auth`. The import is
   free at runtime — only the adapter package itself never declared or used it.

## The fix (3 metadata/code files + 1 new test file)

### 1. `packages/integration-adapters/src/integration_adapters/_http.py`

```python
# BEFORE (lines 1-20)
"""Tiny async HTTP helper for the live adapters (one place for timeout/errors)."""
from __future__ import annotations

import httpx

_TIMEOUT = 8.0


async def post_json(base_url: str, path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_json(base_url: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

# AFTER
"""Tiny async HTTP helper for the live adapters (one place for timeout/errors).

The adapters are INTERNAL callers: the sims (and any in-platform stand-in) gate on
``X-API-Key`` via service_auth.require_internal_key. ``internal_headers()`` returns {} when
INTERNAL_API_KEY is unset, so dev/tests are untouched; it is read per-request, so key rotation
needs no restart of the caller.
"""
from __future__ import annotations

import httpx
from service_auth import internal_headers

_TIMEOUT = 8.0


async def post_json(base_url: str, path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(
        base_url=base_url, timeout=_TIMEOUT, headers=internal_headers()
    ) as client:
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_json(base_url: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(
        base_url=base_url, timeout=_TIMEOUT, headers=internal_headers()
    ) as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()
```

**Why `from service_auth import internal_headers` and not a third local copy:** the helper exists
for exactly this call shape, its behavior is pinned by `packages/service-auth/tests/test_service_auth.py:19-24`
(`{}` when unset, `{"X-API-Key": key}` when set), and the eight worker clients already use it.
Single source of truth beats a third replication of the mcp-servers' local copy.

### 2. `packages/integration-adapters/pyproject.toml` (line 6)

```toml
# BEFORE
dependencies = ["domain-core", "httpx==0.28.1"]

# AFTER
dependencies = ["domain-core", "service-auth", "httpx==0.28.1"]
```

Safe everywhere: all 12 Dockerfiles install `service-auth` in the same `RUN pip install` layer as
`integration-adapters` (verified: `execution-service/Dockerfile:8` and the identical shared line in
the other 11), and CI installs both in one command (`.github/workflows/ci.yml:42-44`). `service-auth`
has no third-party deps of its own beyond FastAPI, which every adapter consumer already has.

### 3. `scripts/run_tests.py` — integration-adapters target gains service-auth on PYTHONPATH

The package suite runs with explicit PYTHONPATH (offline contract). It now imports `service_auth`
transitively through `_http.py`, so its target line must say so:

```python
# BEFORE
    ("packages/integration-adapters", ["../domain-core/src"], "tests"),

# AFTER
    ("packages/integration-adapters", ["../domain-core/src", "../service-auth/src"], "tests"),
```

This is the P1-3 single-inventory contract: `make test` and CI both run `run_tests.py`, so this one
line updates both. Nothing else in CI changes.

### 4. New test — `packages/integration-adapters/tests/test_internal_auth.py`

Style matched to the existing `test_adapters.py` (plain pytest functions, `monkeypatch`,
`asyncio.run`, no network, no fixtures):

```python
"""The live adapters are internal callers: X-API-Key goes out iff INTERNAL_API_KEY is set.

Offline: httpx.AsyncClient is replaced with a recording stub, so no socket is opened and the
sims are not needed. The contract pinned here is the one the sims enforce app-wide via
service_auth.require_internal_key.
"""
from __future__ import annotations

import asyncio

import integration_adapters._http as http_layer


class _FakeResponse:
    def raise_for_status(self) -> None: ...
    def json(self) -> dict: return {"ok": True}


class _RecordingClient:
    sent: list[dict] = []

    def __init__(self, **kwargs) -> None:
        self.sent.append(kwargs.get("headers") or {})

    async def __aenter__(self): return self
    async def __aexit__(self, *args) -> bool: return False
    async def post(self, path, json): return _FakeResponse()
    async def get(self, path, params=None): return _FakeResponse()


def test_key_set_sends_header(monkeypatch) -> None:
    _RecordingClient.sent = []
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    monkeypatch.setattr(http_layer.httpx, "AsyncClient", _RecordingClient)
    asyncio.run(http_layer.post_json("http://sim", "/x", {}))
    asyncio.run(http_layer.get_json("http://sim", "/x"))
    assert _RecordingClient.sent == [{"X-API-Key": "s3cret"}, {"X-API-Key": "s3cret"}]


def test_key_unset_sends_no_header(monkeypatch) -> None:
    _RecordingClient.sent = []
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setattr(http_layer.httpx, "AsyncClient", _RecordingClient)
    asyncio.run(http_layer.post_json("http://sim", "/x", {}))
    assert _RecordingClient.sent == [{}]
```

---

## Validation (run in this order)

1. **Static + offline suite**

   ```bash
   ruff check packages/integration-adapters scripts/run_tests.py
   python scripts/run_tests.py
   ```

   Expected: ruff clean (integration-adapters is not on any grandfather list — keep it that way);
   all suites green including `packages/integration-adapters` (now 41 existing lines of tests +
   2 new tests). If the integration-adapters suite fails with `ModuleNotFoundError: service_auth`,
   step 3 above was skipped — that is the canary proving the PYTHONPATH line is load-bearing.

2. **Live-stack functional proof (the 403 reproduction, inverted):**

   ```bash
   # a) confirm the sims still reject unauthenticated callers (contract unchanged)
   curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8111/sim/roaming \
     -H "Content-Type: application/json" \
     -d '{"customer_id":"x","enable":true,"idempotency_key":"k"}'
   # expect: 403 (with INTERNAL_API_KEY set in the stack)

   # b) rebuild the one runtime consumer and run a real live-mode action
   docker compose -f infra/docker-compose/docker-compose.yml \
                  -f infra/docker-compose/docker-compose.apps.yml up -d --build execution-service
   ```

   Then drive `ExecutionService.execute()` with `CONNECTOR_MODE=live`,
   `action_type="ACTIVATE_ROAMING"`, `payload={"enable": true}` against the same seeded
   subscription used in the P2-4 proof (`68b19707-371d-4f92-9632-0b947e036bdb`):

   - **Before this patch:** 403 from provisioning-sim, action `failed` (observed during P2-4).
   - **After:** `status=executed`, reference `ROAM-…` from the **sim** (not `MOCK-ROAM-…`),
     `provisioning.provisioning_requests` row written by the sim, `roaming_enabled=true`.

   ```sql
   SELECT action_type, status, adapter_reference FROM execution.action_ledger
     ORDER BY created_at DESC LIMIT 1;   -- expect: ACTIVATE_ROAMING / succeeded / ROAM-...
   ```

3. **Grep gates**

   | Gate | Expected |
   |---|---|
   | `grep -rn "internal_headers" packages/integration-adapters/src` | `_http.py` only (one place) |
   | `grep -c "internal_headers" apps/agent-worker/src/clients/*.py` | unchanged (0 for `__init__.py`, ≥2 for the eight clients) |
   | `grep -n "service-auth" packages/integration-adapters/pyproject.toml scripts/run_tests.py` | one hit each |

---

## Regression risk assessment

| Change | Blast radius | Risk |
|---|---|---|
| `_http.py` adds `headers=internal_headers()` | All six live adapters | Near zero in dev/test: `internal_headers()` is `{}` when the key is unset, and the secured stack is exactly where calls were 403ing. Mock adapters make no HTTP calls — untouched. |
| pyproject dependency line | Install metadata only | Zero: every install site already installs `service-auth` alongside. |
| `run_tests.py` PYTHONPATH line | Offline test harness | Zero at runtime; single-inventory contract preserved. |

**Trust-boundary caveat (documented, accepted):** after this fix the internal key rides every
request to whatever `*_ADAPTER_URL` is configured — including `GLPI_ADAPTER_URL`, `CRM_ADAPTER_URL`,
`PAYMENT_ADAPTER_URL`, which point at external systems in a real deployment. Today this is
theoretical: ticketing flows through the ticketing-glpi MCP server's own client (not
`LiveGlpiAdapter`), no runtime caller exists for the payment/CRM adapters, and every wired URL in
the sim stack is an in-platform container. When real carrier systems replace the sims, adapter
auth becomes per-system carrier credentials — a separate design, deliberately **not** bundled here.
`crm_adapter.py`'s inline httpx clients (`:78`, `:97`, duplicating `_TIMEOUT = 8.0` at `:22`) are
intentionally untouched: dormant, external-targeted, and outside this bug's blast radius.

## Explicit non-goals (do not "improve" while applying)

- No change to `require_internal_key` or the sims — the server contract is correct.
- No trace-context injection in `_http.py` (the worker clients' `inject_trace_context` pattern) —
  observability nicety, not part of this bug.
- No refactor of `crm_adapter.py` onto `_http.py` — dormant code, separate cleanup.
- No per-adapter auth config — that's the future real-carrier design, noted above.
- No rebuild of the other 11 images — they never call adapters at runtime (verified: the only
  `get_*_adapter` callers outside the package are in `execution-service/executor.py`).
