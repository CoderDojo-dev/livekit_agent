# Version 107 — Reference catalog writes + outage management, callback session correlation fix

> **Base branch:** `version_106` (`b694397`, pushed state)
> **Commits:** 2 — catalog + outages + correlation fix `585f458`, version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0020_ticket_admin_note`)
> **Rebuild:** business-api (new reference/outages endpoints), agent-worker (callback task fix), admin_dashboard web bundle

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | business-api: `main.py` (+301, 11 new routes), `repositories.py` (+306, catalog + outage methods); agent-worker: `tasks/callback_schedule_task.py` (session correlation fix) |
| Frontend builds       | admin_dashboard: 8 files changed; 2 new components (`catalog-edit.tsx`, `outage-manager.tsx`) |
| alembic head          | `0020_ticket_admin_note` (unchanged)                          |

---

## What's New in This Branch

### Reference catalog writes (`585f458`)

- **Full CRUD on the reference catalogs** (business-api, audit-ledgered via `_audit_reference`):
  - `POST/PATCH/DELETE /api/v1/reference/products[/{product_code}]` — `ProductPayload`/`ProductUpdatePayload`
  - `POST/PATCH/DELETE /api/v1/reference/recharges[/{code}]` — `RechargePayload`/`RechargeUpdatePayload`
  - `POST/PATCH/DELETE /api/v1/reference/geo-areas[/{area_code}]` — `GeoAreaPayload`/`GeoAreaUpdatePayload`
- Repository layer: `create_product`/`update_product`/`delete_product`, same trio for recharges and geo areas.

### Outage management (`585f458`)

- `POST /api/v1/outages` (201), `PATCH /api/v1/outages/{outage_id}`, DELETE — `OutagePayload`/`OutageUpdatePayload` (area_code, severity, cause).
- Repository: `list_outages(active_only, limit)` / `create_outage` / `update_outage`.
- Admin dashboard: `outage-manager.tsx` (new) — declare/resolve outages from the console so the voice agent stops promising service in a down area.

### Callback session correlation FIX (`585f458`)

- `callback_schedule_task.py` now stamps callbacks with **the DB session id** (`session_db_id`), not the agent-local one. Same bug class as v105's guarded-action fix: a callback stamped with the agent-local id cannot be joined back to the call that produced it, so the console could never show which conversation asked for the callback. Fallback keeps prior behaviour if the row does not exist yet.

### Admin dashboard

- `catalog-edit.tsx` (new) — create/edit/delete products, recharges and geo areas against the new endpoints.
- `reference.tsx` rebuilt (+ `reference.server.ts`, `query-keys.ts`); `transcript.tsx`, `metric-card.tsx`, `calls.tsx`, `policies.tsx` polish.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_107` → **GREEN, exit 0** — 215 + 156 + 10 + 17 = **398 passed**, 0 failed.
- First run hit an environment outage (dev Postgres container had been removed mid-run → 103 connection errors, then one health-probe failure while the composition restarted); re-run on healthy infra is fully green.
- Version_106 on remotes untouched (`b694397`).