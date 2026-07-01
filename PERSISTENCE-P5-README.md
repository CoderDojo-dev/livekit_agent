# Persistence — P5: Ticketing mirror + Notification log

The last two in-memory side-effects are now durable. Every ticket the agent opens and every written
confirmation it sends is recorded in Postgres — without losing the no-DB demo path.

## What shipped (10 files)
- **Models** — `ticketing.tickets` (spec §10: a thin local mirror that points at the real GLPI id,
  GLPI stays source of truth) and `billing.notifications` (spec §5.2: the dispatch log). DDL verified.
- **Migration `0005_ticketing_notif`** — the two tables.
- **Ticketing mirror** (`adapters/mirror.py`) — best-effort, DATABASE_URL-gated functions
  (`mirror_create` / `mirror_resolve` / `read_status` / `read_for_customer`). The MCP tools now write
  the mirror on create/resolve and **read it first** on status/lookup, **falling back to the in-memory
  mock** when no DB is configured — so the server runs either way and survives restarts when a DB is present.
- **Notification log** — `NotificationService.notify` writes a `billing.notifications` row after each
  send (best-effort, DATABASE_URL-gated, off-thread). The in-memory `/sent` list is kept for inspection.

## Why this shape
- **GLPI/notifier stay authoritative**; Postgres is the durable local record (mirror / log), exactly
  as the spec frames ticketing (§10) and the notification dispatch log (§5.2).
- **No hard dependency on the DB**: both writes are gated on `DATABASE_URL` and wrapped best-effort, so
  a missing/down database degrades to the prior in-memory behaviour instead of failing a call.
- **Idempotent mirror**: `mirror_create` no-ops if the `glpi_ticket_id` already exists.

## Apply & run
```bash
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
( cd packages/persistence && alembic upgrade head )                 # applies 0005
pip install -e packages/persistence                                  # for both services
# ticketing MCP (:8202) and notification-service (:8106) pick up DATABASE_URL from the environment
```

## Proving it
Open a ticket via the agent (an unresolved technical issue), then:
```sql
SELECT glpi_ticket_id, category, status, subject, last_synced_at FROM ticketing.tickets ORDER BY created_at DESC;
SELECT channel, template_code, status, sent_at FROM billing.notifications ORDER BY sent_at DESC;
```
Resolve it in-call and re-query: the mirror row flips to `resolved`. Restart the MCP server and call
`get_ticket_status` — it now answers from the durable mirror, not lost in-memory state.

Offline (no DB): ticketing mirror **2** + notification **3** pass, plus policy 10 / execution 5 /
context 4 / audit-trail 3 / conversation+sentiment 6. The DB writes are exercised against live Postgres above.

## Notes
- No Postgres in the build sandbox: verified offline what's verifiable (DDL render, mapper resolution,
  the pure `normalize_category` + DATABASE_URL gating, all suites). Durable writes are exercised when
  the services run against `localhost:15432`.
- **State of the data layer:** 23 tables across all 12 schemas; 5 migrations. Every agent read **and**
  write — identity, billing, balance, verdicts, actions, audit chain, conversation, domain effects,
  tickets, notifications — is now real Postgres. The remaining spec surface is back-office, not agent path.
- **Next — P6 (final data slice):** `reference.*` catalogs (incl. the versioned business rules Policy
  consumes), the `business-api` read/admin endpoints (spec §17), and the cross-domain integrity +
  audit-chain verification job (spec §20). Redis cache + Qdrant wiring follow as an ops/perf pass.
