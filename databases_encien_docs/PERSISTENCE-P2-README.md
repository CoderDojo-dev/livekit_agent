# Persistence — P2: the Safety Core on Postgres

Every sensitive action now leaves a durable, tamper-evident trail: a **policy verdict**, an
**idempotent action-ledger row referencing that verdict**, and a **hash-chained audit entry** —
all in Postgres, all in one transaction. No action exists without a verdict (spec §12).

## What shipped (25 files; obsolete in-memory files deleted)
- **Models** — `policy.policy_verdicts`, `execution.action_ledger` (UNIQUE `idempotency_key`,
  FK → `policy.policy_verdicts`), `audit.audit_ledger` (BIGINT IDENTITY `seq`, CHAR(64) hashes),
  `audit.pii_token_map`. (DDL verified against the Postgres dialect.)
- **Migration `0002_safety_core`** — creates the four tables in the existing policy/execution/audit
  schemas + the `action_ledger.updated_at` trigger.
- **audit-trail** — new `PgAuditLedger`: reads the prior `entry_hash`, computes
  `sha256(prev | canonical(payload) | ts)`, inserts append-only, serialized by a transaction-scoped
  advisory lock so concurrent appends can't fork the chain. `verify()` recomputes the whole chain.
  The pure hashing + in-memory ledger stay for tests.
- **policy-service** — `PolicyService(session)` now **persists every verdict** (`policy_verdicts`)
  **and audits it**, atomically, and returns a `verdict_id`. `/audit/verify` runs over the DB chain.
- **execution-service** — `ExecutionService(session)` writes the `action_ledger` (idempotency via the
  UNIQUE key, with a race-safe replay), carries `policy_verdict_id` (FK), dispatches, marks
  `succeeded`, and audits — one transaction.
- **worker** — `guarded_action` threads `verdict_id` (and `customer_id`/`subscription_id`) from
  Policy into Execution; it refuses to execute an AUTHORIZED action that lacks a persisted verdict id.

**Deleted:** `policy_service/audit.py`, `execution_service/audit.py`,
`execution_service/idempotency.py`, `execution_service/tests/test_execution.py` (superseded by the DB).

## Apply & run
Unzip at repo root, apply the migration, then run the services with `DATABASE_URL` pointing at your
Postgres (port **15432** in your environment).

```bash
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
pip install -e packages/persistence -e packages/audit-trail
( cd packages/persistence && alembic upgrade head )          # applies 0002 (safety core)

cd services/policy-service    && pip install -e . && uvicorn policy_service.main:app    --port 8104
cd services/execution-service && pip install -e . && uvicorn execution_service.main:app --port 8105
```
(context-service from P1 stays on 8101; the worker is unchanged except for the client wiring.)

## Proving it
Run a guarded action end to end (e.g. a deferral for Amine via the agent), then:
```bash
curl localhost:8104/audit/verify      # {"intact": true, "entries": N}
curl localhost:8105/audit/verify      # {"intact": true, "entries": M}
# In psql:
#   SELECT requested_action, verdict, rule_id FROM policy.policy_verdicts ORDER BY created_at DESC;
#   SELECT action_type, status, idempotency_key, policy_verdict_id FROM execution.action_ledger;
#   -- a retried action reuses the same idempotency_key -> exactly one row, replay=true
#   SELECT seq, event_type, left(entry_hash,12) FROM audit.audit_ledger ORDER BY seq;
```
Offline (no DB): policy **10**, execution 2, audit-trail 3, context 4 — all pass. The persisted
verdict/ledger/chain are exercised against live Postgres by the steps above.

## Notes
- **Append-only by role** (spec §19): grant `INSERT, SELECT` only on `policy_verdicts`,
  `action_ledger`, `audit_ledger` to the service roles (dev uses the single `telecom` user; role
  hardening is a P4 ops step).
- **session_id** must be a UUID; non-UUID values are coerced to a stable `uuid5` so the demo never breaks.
- The `billing.py`/`ocs.py` relationship additions match your P1 seed fix and are included for a
  self-consistent tree.
- **Next — P3:** conversation persistence (async writer for `call_sessions`/`turns`/`sentiment`/
  `escalation`/`callbacks`), the billing/ocs/sim **write** tables, ticketing mirror, notification log.
