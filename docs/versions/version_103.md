# Version 103 — Admin dashboard console preferences, E.164 phone rendering, note banner, customer mix

> **Base branch:** `version_102` (`c9bd0cd`, pushed state)
> **Commits:** 2 — console preferences + phone rendering `3b815f8`, version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** admin_dashboard web bundle (console preferences, E.164 phone rendering, customer mix)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none (frontend-only version)                                  |
| Frontend builds       | admin_dashboard: 27 files changed +827/−173; 6 new files      |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |

---

## What's New in This Branch

### Console preferences (`3b815f8`)

- `lib/nexus/preferences.ts` — presentation settings store **ported deliberately from the customer portal** `lib/preferences.ts` (same validation discipline, same pre-paint boot script, same `useSyncExternalStore`), so both frontends behave identically. Console-only settings: theme (dark/light), density (comfortable/compact), text size (default/large). Nothing is sent to a server — pure rendering choices applied as a data-attribute on `<html>`.
- `theme-toggle.tsx`, `setting-row.tsx` (new), `preferences` wired through `__root.tsx` + `styles.css`.
- `app-topbar.tsx`, `app-sidebar.tsx` — theme/density aware.

### E.164 phone rendering (`3b815f8`)

- `format.ts` — **`maskPhone` replaced by `formatPhone`**. The old `maskPhone` was broken for the stored format: for `"+21626078277"` (no spaces) `phone.indexOf(" ")` is `-1`, so the head extraction dropped a single trailing character and the output duplicated the last four digits.
- The fix is deliberate and documented: an operator console has `/callbacks` so an advisor can ring the person back, and a masked number cannot be dialled — the rendering is now the **unmasked, grouped E.164 number** (`+216 26 078 277`): country codes longest-first (966, 971, 216, 213, 212, 218, 44, 49, 39, 34, 33, 20, 1), subscriber digits grouped in threes from the right (NANP 3-3-4 for 10 digits, orphan digit merged into the following group). Transcripts remain PII-masked at capture on the backend — that protection is untouched and separate.
- `format.test.ts` (new) — covers the grouping/edge cases.

### Note banner & customer mix

- `note-banner.tsx` (new) — note banner component (used across rebuilt routes).
- `lib/api/customer-mix.server.ts` (new) — honest customer status distribution: the customers list carries no per-status breakdown, so the server fn asks for each status with `limit=1` and reads the totals back.

### Routes rebuilt with shared primitives

- `action-ledger.tsx`, `customer-detail.tsx`, `retrieval-probe.tsx`, `service-health-panel.tsx`, `transcript.tsx`, `audit-page.tsx`, `brand-mark.tsx`, `blocks.tsx`, `primitives.tsx`, `availability-view.ts`, `callback-view.ts`, `query-keys.ts`, `use-adaptive-page-size.ts`, `__root.tsx`, `availability.tsx`, `callbacks.tsx`, `calls.tsx`, `customers.tsx`, `knowledge.tsx`, `notifications.tsx`, `settings.tsx`, `tickets.tsx`, `styles.css` (+128/−).

---

## Validation

- `scripts/test_committed.ps1 -Ref version_103` → **GREEN, exit 0** — 204 + 145 + 10 + 17 = **376 passed**, 0 failed.
- Version_102 on remotes untouched (`c9bd0cd`).