# Version 92 — Frontend regression-test foundation (Vitest), escalation customer identity, backend verified fixes (P2-4/5/6), CI frontend-test job

> **Base branch:** `version_91` (`acda0f8`)
> **Commits:** 4 (Batch 6 foundation `6e1a8b3` + lot `022ecd9` + CI job `e05e0cc` + specs `8b79401`)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** admin_dashboard devDeps added (`vitest@4.1.10`, `@vitest/coverage-v8@4.1.10`, `jsdom@30.0.1`, `@testing-library/react@16.3.2`, `@testing-library/jest-dom@7.0.0`, `@testing-library/user-event@14.6.1`, exact-version); `integration-adapters` now depends on `service-auth`
> **Migration:** none (head stays `0017_notification_failure_reason`)
> **Rebuild:** required — execution-service + agent-worker (P2-4/5/6); admin_dashboard rebuilt on deploy
> **New CI job:** `frontend-test` (typecheck/lint/vitest/build on admin_dashboard)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| livekit-server        | `v1.8.4` (unchanged)                                          |
| Backend service code  | execution-service (`projections.py` P2-4+P2-6), agent-worker (`settings.py`/`session_state.py`/`guarded_action.py` P2-4), integration-adapters (`_http.py` P2-5) |
| Image rebuild         | **execution-service**, **agent-worker**; admin_dashboard web bundle on deploy |
| alembic head          | `0017_notification_failure_reason` (unchanged)                |
| New npm devDeps       | vitest 4.1.10 + jsdom 30.0.1 + @testing-library/react 16.3.2 + jest-dom 7.0.0 + user-event 14.6.1 + coverage-v8 (exact pins, lockfile committed) |
| New Python dep        | `integration-adapters` → `service-auth`                       |
| New CI job            | `frontend-test` (ubuntu, node 22.12, npm ci, typecheck, lint, `npm test`, build) |

---

## What's New in This Branch

Six applied work items — three admin-dashboard batches, three backend verified
fixes — plus the CI wiring for the new frontend test suite.

### Batch 4 — Frontend correctness & keyboard accessibility (admin_dashboard)

- **`knowledge.server.ts`** — `knowledgeApi` transport rewrite: body/formData
  mutual-exclusion guard (500), `AbortController` + timeout, `X-API-Key` only from
  server-side `INTERNAL_API_KEY`, `Content-Type: application/json` **only** for
  JSON bodies (never multipart). Live-verified end to end: health (5 checks ok),
  documents (18/296), probeSearch (real corpus passage), upload multipart
  (ingested + repeated upload = unchanged), purge (archived/deactivated/removed),
  role gates (conseiller 403 on documents/probe; 403 on upload/purge).
- **`advisors.tsx`** — central query keys.
- **`customers.tsx` / `agents.tsx`** — keyboard-accessible rows.
- **`blocks.tsx`** — `LineChart` hardening + conditional `BarChart` removal.

### Batch 5 — Escalation customer identity projection (backend + frontend)

- **`repositories.py`** — `_ESCALATION_LIMIT = 200`; shared `_project_escalation_cases()`
  (precedence `EscalationCase.customer_id` → `CallSession.customer_id` → `null`),
  batched lookups (exactly 3 SELECTs flat as the fallback set grows), filter-before-limit
  on `escalations()`, `close_escalation()` via the shared projection.
- **`escalations.server.ts`** — DTO gains `customer_name`/`customer_vip` (list + close share).
- **`escalation-view.ts`** — `escalationCustomerName/Id/SearchText`; search now covers customers.
- **`routes/escalations.tsx`** — search placeholder, list identity block, detail
  "Customer" block before Session, VIP token only for literal `true`, no customer link.
- **NEW `test_escalation_customer_projection.py`** — 8 tests: precedence matrix,
  dangling ids, soft-deleted customer, query-count bound, ordering/filtering/cap,
  close idempotency, close route + audit payload, RBAC.

### Batch 6 — Frontend regression-test foundation (Vitest/jsdom)

- **`package.json`** — exact-version devDeps (above) + `test`/`test:watch`/
  `test:coverage`/`typecheck` scripts; existing scripts preserved.
- **`package-lock.json`** — committed (npm ci re-installs cleanly, 507 packages).
- **`vitest.config.ts`** — standalone config (`@` alias, jsdom, globals, setup,
  v8 coverage) that does NOT import the app Vite config.
- **`src/test/setup.ts` + `src/test/render.tsx`** — jest-dom matchers, cleanup,
  mock resets, `makeTestQueryClient()` (retries disabled, `gcTime: Infinity`) +
  `renderWithQuery()` — fresh QueryClient per test.
- **`components/escalations/escalations-page.tsx`** — route extraction (body
  byte-identical, page-local constants + `escalationKeys` factory, all exported).
- **`routes/escalations.tsx`** — reduced to route metadata + component registration
  (head byte-identical; `routeTree.gen.ts` untouched).
- **Tests: 21 total** — 13 pure helper (`escalation-view.test.ts`: null-resolution
  = open, resolved = closed, identity fallbacks, search matrix, whitespace
  normalization, dossier unsearchable) + 8 UI (`escalations-page.test.tsx`:
  identity/VIP row-scoped, unresolved fallbacks, search filter, close mutation,
  cache invalidation with `escalationKeys.list("open")` not `"all"`,
  loading/error/retry/empty, customer-before-session DOM order).
- **`ci.yml`** — new `frontend-test` job wiring all four scripts.
- **`.gitignore`** — `coverage/` ignored.

### P2-4 — Verified fixes: roaming projection, port defaults, duplicate window

- **`projections.py`** — `ACTIVATE_ROAMING` honors `payload["enable"]` (mirrors
  executor.py live dispatch; before: `roaming_enabled` stayed `true` on disable).
- **`settings.py`** — `business_api_url` default 8107→**8108**, `nms_service_url`
  default 8108→**8110**; `.env.example` updated (`NMS_SERVICE_URL=…:8110`, stale
  commented 8107 line removed).
- **`session_state.py` / `guarded_action.py`** — post-success duplicate window:
  `_DUPLICATE_WINDOW_S = 60.0`, `_completed_at`, `new_idempotency_key` window
  logic, `release_idempotency_key` → `mark_operation_completed`.
- **NEW `test_idempotency_window.py`** — 5 unit tests.
- Live proof (mock connector): disable direction now flips `roaming_enabled` → `f`
  with `{"enable": false}` in provisioning_requests + action_ledger; enable still `t`.

### P2-5 — Verified fix: live adapters authenticate to the internal sims

- **`_http.py`** — `internal_headers()` from `service-auth` injected into both
  `post_json` and `get_json` httpx clients (fixes the 403 observed in P2-4's live
  path; inert `{}` when `INTERNAL_API_KEY` unset).
- **`pyproject.toml`** — `service-auth` dependency added.
- **`run_tests.py`** — integration-adapters suite PYTHONPATH includes `../service-auth/src`.
- **NEW `test_internal_auth.py`** — 2 unit tests.

### P2-6 — Verified fix: live-mode projection reconciliation (dual-write)

- **`projections.py`** — probe-first early-skips: `deferral_probe_keys(key)`,
  `_effect_applied`/`_deferral_applied` (one SELECT on the UNIQUE idempotency_key),
  applied to `_payment`, `_payment_plan` (deferral from **current** dates — never
  push due dates twice), `_recharge` (credits + bonus once), `_sim_case`, `_sim_order`
  (probes `ProvisioningRequest` — the sim keys the request), `_provisioning`
  (one early-skip for CHANGE_PLAN + ACTIVATE_ROAMING). Non-goals respected: no
  `ON CONFLICT`, no `is_live()` branches, no service.py SAVEPOINT change.
- **`test_projections.py`** — `deferral_probe_keys` import + test.
- Live proof (6 actions, fresh verdicts, `p26-live-proof`): payments row = 1
  (was collision + `projection_failed`), deferral +7 not +14, top-up +5.00 exactly
  once, SIM order 1 (was 2), roaming follows payload, plan change 1 per change;
  **0 `projection_failed` audit entries** (was one per action); mock-mode
  byte-identical (FIFO settle 17.50 → 12.50, 1 payments row).

---

## Validation

- `test_committed.ps1 -Ref version_92` (clean export): **210/210 PASS**
  (business-api **74** — +8 escalation projection tests, agent-worker **109** — +5
  idempotency window, notification 10, policy 17)
- Full inventory `run_tests.py`: **all 18 suites passed** (incl. the 2 new
  adapter auth tests); ruff clean on all touched Python
- admin_dashboard: `tsc --noEmit` 0 errors · `npm run lint` 0 errors (9
  pre-existing warnings) · `npm test` **21 passed** · `npm run build` success
- Live proofs: knowledge BFF full RAG lifecycle; escalation identity projection
  (3 SELECTs flat, precedence verified); revoke/audit unchanged; P2-4/P2-5/P2-6
  live-stack matrix all PASS
- Grep gates: `_effect_applied|_deferral_applied` 8 hits; `DEFERRAL::` only in
  `ledger.py` (writer) + `projections.py` (probe) + test literal

### Environment notes (recurring, documented in reports)

- Retention tests needed a live-DB purge of stale `auth.portal_sessions` rows
  (exact-count asserts vs live DB) — same pre-existing condition as P2-5, purged
  per the retention job's own criteria, no code change.
- `.env` (gitignored): added `POLICY_PLAN_CODES=["FIBER","FLEXI","TRANKIL"]`
  (JSON-array form required by pydantic-settings 2.7.1) so a `CHANGE_PLAN`
  verdict can mint — deployment config only, not in this branch.

---

## Out of scope / notes

- `CLIENT_PORTAL_cookbook.md` is **PLAN ONLY** (no code written) — not committed.
- Live adapter 403 on `provisioning-sim:8109` was the P2-4 live-path gap now
  closed by P2-5; `CONNECTOR_MODE=live` roaming proof follows the same code path.
- Pre-existing env debt (`.venv` launcher, knowledge-service H-6) unchanged from
  v91 — documented in the P2-3 spec.