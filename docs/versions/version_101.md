# Version 101 — Preferred language self-service, preferences store, conversation cadence ticks, portal polish

> **Base branch:** `version_100` (`69c591b`, pushed state)
> **Commits:** 3 — revert grid background `4a9585c`, main feature work `657fad2` (verify hash at push time), version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** business-api (new `/me/profile/language` endpoint + `me_writes`), customer_portal web bundle

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | business-api: `me_writes.py` (new module), `main.py` (+45, PUT `/api/v1/me/profile/language` with audit ledger), `test_me_preferred_language.py` (new) |
| Frontend builds       | customer_portal: preferences store, cadence ticks, theme toggle, motion/nav-count hooks, assistant live-stream, orb, activity, styles |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |

---

## What's New in This Branch

### Preferred language self-service (`657fad2`)

- **`PUT /api/v1/me/profile/language`** — customer sets their own preferred agent language. `customer_id` comes from the authenticated principal (nothing in the request to tamper with: client A cannot change customer B's preference). Writes `crm.customers.preferred_language` — the exact column `config/language_policy.resolve_session_language` reads as the *saved preference* candidate; precedence unchanged: explicit in-conversation request > saved preference > French default.
- **`me_writes.py`** — the mirror of `me_reads`, scoped by the TOKEN, never by the URL. One function per writable field (deliberately narrow: identity/commercial data is not editable from a browser).
- **Audit** — `PgAuditLedger.append` on change (`me_preferred_language_changed`, previous + new value, `entity_reference=customers:<id>`).
- **Errors** — 400 `UnsupportedLanguage`, 404 customer not found.
- **Tests** — `test_me_preferred_language.py` (new).

### Preferences store (`657fad2`)

- `preferences.ts` is now the store: `useSyncExternalStore` so a change on the preferences screen reaches the shell, assistant and every mounted surface **without a reload**.
- Validated coercion (`pick`/`coerce`) — storage is user-writable and survives deploys: unrecognised theme must never reach `<html data-theme>` unmatched by stylesheet rules; legacy `nexus_portal_preferences` key still read, writes go to `portal_preferences` only.
- `theme-toggle.tsx`, `preferences.test.ts` (new), `preferences.tsx` (+130), `use-portal-motion.ts`, `use-nav-counts.ts` (new hooks).

### Conversation cadence ticks (`657fad2`)

- `conversation.ts` — `cadenceTicks()`: one tick per turn, no interpolation. **timed: true** when every turn carried a parseable `at` (x = real time offset); **timed: false** when stamps are missing/unparseable/identical (x = turn order; the label must say timing is unknown rather than implying a recorded timeline). `conversation.test.ts` (+83).

### Portal polish (`657fad2`)

- `live-stream.tsx` (+20), `orb.tsx`/`orb-renderer.ts` (orb stage), `activity.tsx` (+94), `services.tsx`, `assistant.tsx`, `portal-rail.tsx`, `portal-tabbar.tsx`, `data.tsx`, `primitives.tsx`, `copy.ts`, `me.server.ts` (+37), `styles.css` (+101/−) canvas/grid rework.

### Revert of grid background layer (`4a9585c`)

- The background layer added by the previous in-flight process is removed from the client portal UI (keep surface layering intentional).

---

## Validation

- `scripts/test_committed.ps1 -Ref version_101` → **GREEN, exit 0** — 204 + 145 + 10 + 17 = **376 passed**, 0 failed.
- Version_100 on remotes untouched (`69c591b`).