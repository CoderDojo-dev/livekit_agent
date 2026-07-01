# Persistence — P6 (final): Reference catalogs + business-api back-office + integrity job

The last slice closes the data layer: the versioned rule/catalog registry, a real back-office API
for supervisors/admins (spec §17), and the cross-domain integrity + audit-chain job (spec §20).

## What shipped (15 files)
- **`reference.*` models** — `business_rules` (the versioned, governable registry of the Policy
  rules — the deterministic engine still executes in code; this table is the published/audited
  catalog), `error_catalog`, `products`, `recharge_catalog`. **Migration `0006`** + a seed
  (`seed_reference.py`: 6 rules, 2 errors, 3 products, 4 recharges).
- **`apps/business-api`** — a new FastAPI back-office with **9 real §17 endpoints**, RBAC, and the
  integrity job:
  - `GET /api/v1/customers/{id}/360` · `GET /api/v1/sessions/{id}` (masked transcript + sentiment) —
    *conseiller+*
  - `GET /api/v1/escalations` · `/policy/verdicts` · `/actions` · `/kpis` — *superviseur+*
  - `GET /api/v1/audit/verify` · `/reference/business-rules` · `/jobs/integrity` — *administrateur*
  - **RBAC** (`security.py`) enforces the conseiller < superviseur < administrateur matrix (role from
    `X-Role`; ⚠ OIDC binds at integration).
  - **KPIs** (`kpis.py`, pure) — containment rate, escalation rate, avg frustration over the
    persisted conversation record.
  - **Integrity job** (`jobs/integrity.py`, spec §20.4) — cross-domain orphan checks
    (every `customer_id`/`subscription_id` resolves in `crm`) **plus** the `audit_ledger` hash-chain
    re-verification. No endpoint mutates the audit ledger.

## Apply & run
```bash
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
( cd packages/persistence && alembic upgrade head )            # applies 0006
( cd packages/persistence && python -m seed.seed_reference )   # rules/errors/products/recharges
cd apps/business-api && pip install -e . && uvicorn business_api.main:app --port 8108
```

## Proving it
```bash
curl -H 'X-Role: administrateur' localhost:8108/api/v1/jobs/integrity        # orphans + chain intact
curl -H 'X-Role: superviseur'    localhost:8108/api/v1/kpis                  # containment/escalation
curl -H 'X-Role: administrateur' localhost:8108/api/v1/reference/business-rules
curl -H 'X-Role: superviseur'    "localhost:8108/api/v1/escalations?status=open"
curl -H 'X-Role: conseiller'     "localhost:8108/api/v1/sessions/<session_id>"
curl -H 'X-Role: conseiller'     localhost:8108/api/v1/policy/verdicts?session_id=<id>   # 403 (needs superviseur)
```
Offline (no DB): business-api **6** (security/kpis/integrity), plus policy 10 / execution 5 /
context 4 / notification 3 / ticketing 2 / audit-trail 3 / conversation+sentiment 6 — **39 total pass**.
The DB-backed reads/integrity run against live Postgres above.

## Notes / honest caveat
- No Postgres in the build sandbox: verified offline what's verifiable (DDL render, mapper resolution,
  the ORM/orphan queries compiling against the Postgres dialect, RBAC + KPI + integrity pure logic,
  full app import with all 9 endpoints). The DB-backed endpoints + the integrity job run when
  business-api is started against `localhost:15432`.
- **Deliberate deferrals** (noted, not silent): the §17 `POST data-export` workflow and the
  `PUT business-rules` (mutating, audited) endpoint are integration TODOs; `audit/verify` checks the
  whole chain (range filter is a refinement); OIDC replaces the header role at integration.

---

## The data layer is complete (P1 → P6)
| Slice | Delivered |
|---|---|
| P1 | CRM/Billing/OCS read foundation; context-service on Postgres; identity resolver |
| P2 | Safety core: policy verdicts + idempotent action ledger + hash-chained audit (persisted) |
| P3 | Conversation record via a non-blocking async writer (sessions/turns/sentiment/escalation/callback) |
| P4 | Execution write projections (payments/plans/recharges/SIM cases), atomic with the ledger |
| P5 | Ticketing mirror + notification log (durable, with mock fallback) |
| P6 | Reference catalogs + business-api back-office + cross-domain integrity & audit-chain job |

**27 tables across 12 bounded-context schemas, 6 reversible Alembic migrations, 39 offline tests.**
Every agent read **and** write is real PostgreSQL; the canonical UUID identity model (MSISDN resolved
once at the edge) holds end to end; every sensitive action is verdict-checked, idempotent, and
hash-chain audited. Remaining spec surface (Redis cache, Qdrant wiring, live OCS/Billing/Payment/SMS
bindings) is ops/perf and ⚠-bind-at-integration — no schema or query changes, just `CONNECTOR_MODE`.
