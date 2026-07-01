# Persistence — P1: CRM/Billing/OCS read foundation (real Postgres)

First slice of the data layer. The agent's **read/identity path now runs on PostgreSQL**, not mock
lists. See `ADR-0001-data-layer.md` for the full analysis and the P2–P4 plan.

## What shipped (22 files)
- **`packages/persistence`** — shared SQLAlchemy 2.0 layer: `base.py` (UUID PK + timestamps + soft-delete
  mixins, naming convention), `engine.py` (sync engine/session from `DATABASE_URL`), and models for
  **crm** (customers, subscriptions, consent_records, customer_interactions), **billing** (accounts,
  invoices, invoice_items), **ocs** (balance_accounts). Verified: models render the exact spec DDL.
- **Alembic** — `alembic.ini`, `env.py`, and migration `0001` (extensions, **all 12 schemas**,
  `set_updated_at` trigger, crm/billing/ocs tables, the `crm.v_subscription_live` read-through view).
- **`deploy/postgres/docker-compose.yml`** — Postgres 16.
- **`packages/persistence/seed/seed_pilot.py`** — the 3 canonical callers (real TND), FK-safe,
  UUID-resolved at load time. National IDs end in the demo secrets (4087 / 9912 / 2256).
- **context-service** — swapped from `mock_directory` to a Postgres `CrmRepository`. Same wire
  contract (Customer-360 / verify-identity / invoices / balance), plus `subscription_id`,
  `fraud_suspected`, and `GET /internal/context/resolve` (msisdn → UUIDs, §16.2). `mock_directory.py`
  and `aggregator.py` deleted.
- **agent-worker** — `CustomerContext` now carries `subscription_id` + `fraud_suspected`.

## Bring it up
```bash
# 1) Postgres
docker compose -f docker-compose.yml -f deploy/postgres/docker-compose.yml up -d postgres
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:5432/telecom"

# 2) install the shared package + apply schema
pip install -e packages/persistence
( cd packages/persistence && alembic upgrade head )

# 3) seed the pilot data
( cd packages/persistence && python -m seed.seed_pilot )

# 4) run context-service on Postgres (same port 8101)
cd services/context-service && pip install -e . && uvicorn context_service.main:app --port 8101
```

## Verify
```bash
curl "http://localhost:8101/internal/context/resolve?msisdn=+21620155320"   # -> {customer_id, subscription_id, fr}
curl  "http://localhost:8101/context/+21629744108"                          # Yousra (VIP, ar) 360 snapshot
curl  "http://localhost:8101/billing/<customer_id>/invoices"                 # Karim -> 73.900 TND overdue
curl -X POST localhost:8101/verify-identity -H 'content-type: application/json' \
     -d '{"customer_id":"<uuid>","answer":"4087"}'                          # last-4 of national_id (CIN)
```
Offline (no DB): `cd services/context-service && PYTHONPATH="src:../../packages/persistence/src" python -m pytest -q tests/` → 4 passed (pure mapping). The repository reads are validated against the live Postgres above.

## Notes
- **Sync SQLAlchemy**; context-service endpoints are sync `def` (FastAPI threadpools them).
- The other 9 schemas exist (empty) from migration 0001; their tables arrive in P2–P4 as the
  services that own them are migrated. **No mock lists remain in context-service.**
- `DATABASE_URL` is the only binding; in Docker use `postgresql+psycopg://telecom:telecom@postgres:5432/telecom`.
