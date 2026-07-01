# Patch-Set 2 — Persistence completeness (tester report)

Fills the two empty schemas, adds the JSONB GIN indexes, and adds migration-integrity tests — and
crucially **wires the new provisioning schema to real actions** so it isn't dead tables.

## Report items closed (4)
| # | Item | What changed |
|---|---|---|
| 1 🟠 | Empty OSS schema | `models/oss.py`: `network_elements`, `alarms`, `outages` (read models for the NmsAdapter / "known outage in your area?") |
| 2 🟠 | Empty Provisioning schema | `models/provisioning.py`: `provisioning_requests`, `sim_orders`, `plan_change_history` |
| 14 🟡 | Missing JSONB GIN indexes | migration `0008`: GIN on `policy_verdicts.inputs_snapshot`, `action_ledger.parameters`, `escalation_cases.dossier`, `audit_ledger.payload`, `business_rules.definition_json`, `provisioning_requests.parameters` |
| 29 🟡 | No migration tests | `packages/persistence/tests/test_migrations.py`: unique revision ids + a **linear single-root chain** + full model registration (offline). The live `alembic upgrade head` remains a CI gate against real Postgres |

## Not dead schema — provisioning is exercised
The AccountServicesAgent (Patch-Set 1) emits `CHANGE_PLAN` / `ACTIVATE_ROAMING`. Those already route
to the `provisioning` domain, so the **execution write-projection now writes them**:
`execution_service/projections.py` gained a `provisioning` projection → a `provisioning_requests`
row (idempotency_key + policy_verdict_id, like every other projection) plus a `plan_change_history`
row on `CHANGE_PLAN`. This closes the report's note that "`CHANGE_PLAN` maps to provisioning but no
table exists to record it."

## Migrations
- **`0007_oss_provisioning`** — 6 tables + `updated_at` triggers on the mutable ones. Chain:
  `0006_reference → 0007`.
- **`0008_gin_indexes`** — 6 GIN indexes (reversible). Chain: `0007 → 0008`.

## Verification (offline)
- OSS/provisioning DDL renders against the Postgres dialect; **33 tables across all 12 schemas**;
  mappers configure clean; 8 migrations with a valid linear chain.
- Suites: persistence migration tests **3**, execution **5** (incl. `CHANGE_PLAN → provisioning`).
- Apply on your DB: `( cd packages/persistence && alembic upgrade head )` → applies `0007` + `0008`.

## Note (report #28 — patches-dir typo)
The `patches/persistance_*` directory is **not in the repo tree** here — it's a local artifact on
your machine. Rename it there: `git mv patches/persistance_p1 patches/persistence_p1` (etc.). No code
depends on that path.

## Next
- **Patch-Set 3 — Real adapters behind `CONNECTOR_MODE`**: integration-adapters (#3), GLPI REST
  client (#4), SMS/WhatsApp/Email channels (#5), execution dispatch via adapters (#10),
  notification-client (#11), messaging-gateway MCP (#2).
- **Patch-Set 4 — Infra/storage & ops**: Qdrant (#6), Redis (#7), MinIO (#8), Dockerfiles (#30),
  API gateway (#18), CI/CD (#19), Helm (#20), DB backup (#22), secrets (#23).
