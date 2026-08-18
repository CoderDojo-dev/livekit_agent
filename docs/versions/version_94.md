# Version 94 — Client portal cookbooks 8-11 applied, extended platform service-health panel, customer portal /me reads and token-service admission fixes

> **Base branch:** `version_93` (`3faf945`)
> **Commits:** 7 (cookbook 8 `dad9643`, cookbook 9 `eeb6bf9`, cookbook 10 `2bca172`, unused-Query fix `50fd2c2`, ruff/mypy fixes `dcb1cda`, service-health panel + portal deps `48004d6`, cookbooks-v94 docs `10966c9`)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** customer_portal env example extended; no runtime dep bumps
> **Migration:** none (head stays `0018_agent_usage_events`)
> **Rebuild:** business-api (service-health concurrency/cache), token-service (admission request context), customer_portal web bundle on deploy
> **New CI step:** `npm run verify` (verify-portal.sh 12-check guard) added to the CI pipeline

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | business-api (`service_health.py` concurrency + cache TTL, `me_reads.py`, `repositories.py`, `retention.py`, `main.py`), token-service (`main.py` admission request context) |
| Infra change          | `docker-compose.apps.yml`: `SERVICE_HEALTH_TIMEOUT_MS`, new `SERVICE_HEALTH_CACHE_TTL_MS` (15000), `SERVICE_HEALTH_CONCURRENCY` (8); `SERVICE_HEALTH_TARGETS` rewritten — 14 targets with `id`/`origin`/`path`/`probe_kind` (`liveness`/`readiness`/`none`) and `required` flags (ocs-billing-sim, nms-sim, provisioning-sim, ai-knowledge-rag MCP, messaging-gateway MCP, agent-worker added) |
| Image rebuild         | **business-api**, **token-service**; customer_portal + admin_dashboard web bundles on deploy |
| alembic head          | `0018_agent_usage_events` (unchanged)                          |
| New CI step           | `Guard (verify-portal.sh)` — `npm run verify`, 12-check guard enforced on Ubuntu runners before build |

---

## What's New in This Branch

### Cookbook 8 — Correctness and security fixes (`dad9643`)

- business-api `main.py` — removed unused `Query` import (`50fd2c2`); `me_reads.py` / customer portal self-service reads hardened.
- token-service `main.py` — admission flow now carries the request context (`Request`), fixing per-request identity handling in voice admission.
- retention `jobs/retention.py` — session purge behaviour preserved and covered by tests.

### Cookbook 9 — Honest pagination and data depth (`eeb6bf9`)

- `Frontend/customer_portal` — pagination and data-depth views across activity, billing, notifications and voice APIs (`activity.server.ts`, `billing.server.ts`, `notifications.server.ts`, `voice.server.ts`, `config.ts`, `query-keys.ts`); portal pages `activity.tsx`, `billing.tsx`, `help.tsx`, `preferences.tsx`, `services.tsx`, `assistant.tsx` wired to the reads.

### Cookbook 10 — Tab organisation, visibility and honesty (`2bca172`)

- `portal-topbar.tsx`, `portal/data.tsx`, `copy.ts` — tab structure and copy updates for accurate labelling.

### Cookbook 11 — Verification and runtime proof (`dcb1cda`, `48004d6`)

- Pre-existing ruff/mypy findings in committed files fixed (`dcb1cda`).
- `.github/workflows/ci.yml` — `npm run verify` guard (12-check `verify-portal.sh`) added.
- `service-health-panel` (admin_dashboard component + test) and `service-health.server.ts` extended; backend `service_health.py` gained `SERVICE_HEALTH_CACHE_TTL_MS` caching and `SERVICE_HEALTH_CONCURRENCY` (8 parallel probes); `SERVICE_HEALTH_TARGETS` expanded from 8 to 14 targets (simulators, MCP gateways, agent-worker, per-target `probe_kind` and `required`).
- Tests aligned: `test_auth_http.py`, `test_retention_portal_sessions.py`, `test_service_health.py`.
- `packages/persistence/models/__init__.py` and `.env.example` updated to match.

### Cookbook docs (`10966c9`)

- `features_to_apply/client_portal_cookbooks/cookbooks-v94/` — `00-REVIEW-OF-version_93.md` plus cookbooks 08-11 as applied specs (the single documentation commit for this version).

---

## Validation

- `scripts/test_committed.ps1 -Ref version_94` → **GREEN, exit 0** — 132 + 109 + 10 + 17 = **268 passed**, 0 failed.
