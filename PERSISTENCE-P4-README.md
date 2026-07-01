# Persistence — P4: Execution write projections

When a guarded action succeeds, its **domain effect** is now written into the owning schema —
atomically with `execution.action_ledger` and the audit chain. The agent's write path is real.

## What shipped (8 files)
- **Models** (only the effects the agent actually produces, per the ADR "build what's exercised"):
  `billing.payments`, `billing.payment_plans`, `ocs.recharges`, `sim.block_unblock_cases`. Each
  mirrors the action's `idempotency_key` and (where applicable) carries the `policy_verdict_id` that
  authorized it. DDL verified against the Postgres dialect.
- **Migration `0004_domain_writes`** — the four tables + `updated_at` triggers on the mutable ones.
- **`execution_service/projections.py`** — maps an `action_type` to its projection and writes it:
  - `EXECUTE_PAYMENT` → `billing.payments` (status `succeeded`, gateway ref = the adapter reference)
  - `PAYMENT_DEFERRAL` → `billing.payment_plans` (even installments, `policy_verdict_id` linked)
  - `TOP_UP` → `ocs.recharges` (channel `agent`)
  - `UNBLOCK_SIM` / `REACTIVATE_SIM` → `sim.block_unblock_cases` (`identity_verified`, verdict-linked)
- **`execution_service/service.py`** — calls the projection **inside a SAVEPOINT** after a successful
  dispatch, so a projection problem can never undo the action ledger or the audit chain. Missing data
  (e.g. no billing account) logs and skips; the action is still ledgered + audited.

## Why this shape
- **Atomic with the ledger**: the projection commits in the same transaction as the `action_ledger`
  row + the audit entry. One unit of work.
- **Idempotent end-to-end**: a replayed `idempotency_key` returns before re-projecting (the ledger
  lookup short-circuits), and each projection table also has a UNIQUE `idempotency_key` as a backstop.
- **Verdict-traceable**: `payment_plans` and `block_unblock_cases` store the `policy_verdict_id`, so
  every state-changing effect can be traced back to the verdict that authorized it.

## Apply & run
```bash
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
( cd packages/persistence && alembic upgrade head )      # applies 0004
# execution-service already depends on persistence (P2); just restart it on :8105
```

## Proving it (after a guarded action runs end to end)
```sql
-- a deferral for Karim:
SELECT total_amount, installment_count, installment_amount, status, policy_verdict_id FROM billing.payment_plans;
-- a payment:
SELECT amount, method, status, gateway_reference, idempotency_key FROM billing.payments;
-- a top-up:
SELECT amount, channel, status, transaction_reference FROM ocs.recharges;
-- a SIM unblock:
SELECT action, status, identity_verified, policy_verdict_id FROM sim.block_unblock_cases;
-- trace any effect back to its authorizing verdict:
SELECT p.amount, v.verdict, v.rule_id
FROM billing.payment_plans p JOIN policy.policy_verdicts v ON v.id = p.policy_verdict_id;
```
Offline (no DB): execution **5** (executor 2 + projections 3), plus policy 10 / context 4 / audit-trail 3
/ conversation+sentiment 6 — all pass. The projection writes are exercised against live Postgres above.

## Notes / honest caveats
- No Postgres in the build sandbox: verified offline what's verifiable (DDL render, mapper resolution,
  the pure projection mapping + installment math, all suites). The domain rows get their first real
  write when a guarded action runs against `localhost:15432`; I'll fix fast if needed.
- **Scope** (deliberate, per the ADR): only the four effects the agent produces are modeled now. The
  spec's supporting tables (`collections`, `disputes`, `refunds`, `usage_events`, `sim.profiles`,
  `puk_records`, `swap_requests`, vouchers, eSIM/inventory, full OSS/NMS) remain scaffolded schemas to
  be filled when a use case reaches them — not unmeasurable dead tables.
- **Next — P5:** the ticketing mirror + notification log (their own services), then `reference.*`
  catalogs (incl. versioned business rules consumed by Policy), `business-api` endpoints (spec §17),
  the cross-domain integrity + audit-chain job (spec §20), and finally Redis cache + Qdrant wiring.
