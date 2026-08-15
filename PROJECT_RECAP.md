# Project Recap

## Project purpose

A self-hosted telecom customer-support platform built around a real-time LiveKit voice agent, with text support and French, Arabic, and English operation. It applies deterministic policy checks before sensitive actions, integrates with telecom business systems, records consequential activity in a hash-chained audit ledger, and supports human escalation with a complete dossier. Cloud services may provide STT, LLM, and TTS inference; PII, audit data, and business-system access remain self-hosted.

## Architecture and major directories

The system follows Clean/Hexagonal Architecture, DDD, and SOLID principles.

- `apps/` — deployable applications, including the agent worker, business API, token service, customer portal, and admin dashboard.
- `services/` — context, knowledge, decision, policy, execution, notification, and simulator services.
- `packages/` — shared domain, persistence, audit, PII, authentication, storage, integration, notification, and observability libraries.
- `mcp-servers/` — internal knowledge, GLPI ticketing, and messaging integrations.
- `Frontend/admin_dashboard/` — TanStack Start administration and supervision console.
- `infra/` — Docker Compose, Helm, LiveKit, observability, and deployment configuration.
- `docs/` — architecture records and implementation documentation.
- `features_to_apply/` — feature cookbooks and implementation guidance.

The sensitive-action path is `Decision -> Policy -> Execution`; authorized actions are idempotent and audited. The agent worker is a composition root, while vendor-specific LiveKit provider imports remain isolated behind adapters.

## Technology stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL.
- **Real time and AI:** LiveKit with direct STT/LLM/TTS provider plugins and fallback adapters.
- **Frontend:** TypeScript, React, TanStack Start, Vite.
- **Infrastructure:** Docker Compose, Helm, Redis, Qdrant, MinIO, OpenTelemetry.
- **Integration:** Internal MCP servers and typed service clients.
- **Security and integrity:** httpOnly session cookies, server-side API proxying, role gates, PII masking, idempotency keys, and a hash-chained audit ledger.

## Engineering rules and conventions

1. Business rules must not import LiveKit or vendor SDKs; dependencies sit behind domain ports.
2. `apps/agent-worker/src/server.py` contains wiring only, not business logic.
3. No sensitive action may bypass Decision, Policy, or Execution.
4. Policy verdicts must include a result, rule identifier, and justification and must be audited.
5. Preserve execution idempotency, audit locking, transaction boundaries, and projection SAVEPOINT behavior.
6. Keep admin-dashboard API calls server-side; never expose bearer tokens or call business API port `8108` directly from the browser.
7. Protect every server function with authentication/role middleware; route guards alone are insufficient.
8. Register literal FastAPI routes before parameterized routes.
9. Keep frontend styling achromatic; do not add raw RGB or hex colors in new frontend files.
10. Use centralized date/time formatting and disclose the UTC fallback.
11. Portal overlays to `document.body` to avoid transformed-container clipping.
12. Map every backend status explicitly because an unknown `StatusChip` key renders nothing.
13. Do not add dependencies without an explicit decision; preserve the lint-warning baseline.
14. Do not rewrite published admin-dashboard history; keep feature changes independently revertible.

## Current admin-dashboard status

Audit baseline: branch `version_90`, commit `f6063f6`.

The dashboard has a working integration and security substrate and is connected to the business API through server-side functions. The inspected code contains **20 frontend route files**, **23 API files**, and the backend exposes **54 routes**. Authentication uses an httpOnly session cookie, backend-derived roles, normalized API errors, and server-function role enforcement.

The dashboard is functional but not feature-complete. Some modeled backend domains remain unexposed, some operational workflows are read-only, and several production-readiness decisions remain open.

## Completed capabilities

- Login/session integration and server-only business API proxy.
- Role-aware server-function middleware and normalized error handling.
- Advisor registry and availability views.
- Callback queue and callback detail/lifecycle visibility.
- Call history and transcript views.
- Retention endpoint minimum of 30 days, returning `422` below the floor.
- Correct literal-before-parameter ordering for inspected session routes.
- Read-only escalation visibility.
- Existing reference business-rules endpoint and populated reference data in persistence.
- Deterministic policy/execution safeguards, idempotent action handling, PII masking, and hash-chain verification foundations.

## Prioritized remaining work

### P0 — Correctness and security

- Replace the single environment-variable admin credential model with an approved multi-user identity and authorization design.
- Correct host-development service URL defaults for business API and NMS without breaking container overrides.
- Add real service health probes; do not present hardcoded `online` states.
- Preserve and regression-test the server-only token boundary, role derivation, policy checks, execution idempotency, and audit-chain integrity.
- Confirm the intended role for listing sessions (`superviseur` currently receives access; `conseiller` receives `403`).

### P1 — Close core operational workflows

- Implement an approved escalation-resolution workflow; all observed escalations are currently open and no write path closes them.
- Complete tickets, knowledge/RAG, guardrails/policies, decisions/actions, and customer-360 dashboard capabilities where still incomplete.
- Expose approved reference catalogs with explicit role gates; keep `geo_aliases` internal unless requirements change.
- Add real action and audit views with honest empty states where no records exist.

### P2 — Management and observability

- Complete KPI/analytics, audit/integrity/retention, agent management, handoff/escalation, and reference-catalog experiences.
- Clarify and verify percentage formatting contracts and invoice amount semantics.
- Decide whether agent-attributed metrics should include persisted agent turns; current evidence indicates only caller turns are stored.
- Reconcile the current 31 advisor-shift rows with older documentation that referenced 33, without destructive reconstruction.

### P3 — Hardening and maintainability

- Add automated backend and frontend test suites and CI gates.
- Reduce the existing lint warnings without changing the baseline accidentally.
- Reconcile stale port/component documentation with source and deployment configuration.
- Add pagination or virtualization only where measured data growth requires it.

## Verification status

| Check | Status |
| --- | --- |
| Admin-dashboard build | **Passes** |
| TypeScript check | **Clean** in the inspected audit evidence |
| Lint | **0 errors, 9 warnings** |
| Automated tests | **Absent** for the audited dashboard scope |
| Backend routes counted | **54** |
| Frontend route files counted | **20** |
| Frontend API files counted | **23** |

The build and lint results establish compilation and static-analysis health, not behavioral correctness. Missing automated tests remain a material verification gap.

## Known ambiguities and blockers

- The backend has no real multi-user admin store; authentication currently depends on one configured credential pair and role.
- Session-list role expectations conflict between an older runbook and the implemented supervisor-only gate.
- Escalation closure has no approved business workflow or write path.
- Real service health is not probed across all services.
- Some modeled entities remain unexposed, including customer interactions, payments, payment plans, and consent records.
- The automation `/rules` capability is implied by documentation but was not verified as implemented.
- Host-development URL defaults can target the wrong services even though Docker Compose overrides are correct.
- A silent-turn incident could not be tied to a specific in-flight tool, so ticket-tool timeout changes remain blocked on reproduction evidence.
- Existing documentation contains stale service ports and references a dashboard path that does not match the current tree.

## Recommended next implementation sequence

1. Lock down P0 decisions: multi-user auth, session-list role policy, host URL defaults, and real health reporting.
2. Add a minimal automated test harness covering authentication, role gates, route ordering, API error normalization, and dashboard build/lint gates.
3. Implement escalation resolution as a separately approved, audited, idempotent workflow.
4. Complete tickets, knowledge, policies, decisions/actions, and customer-360 vertical slices end to end.
5. Add audit/integrity, KPI/analytics, agent-management, and reference-catalog views using verified backend vocabularies.
6. Resolve metric/data-contract ambiguities, then harden observability, pagination, and documentation.
