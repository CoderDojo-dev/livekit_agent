# Version 108 — Area picker by name, outage manager wiring, metric-card compact variant

> **Base branch:** `version_107` (`b76e818`, pushed state)
> **Commits:** 2 — area picker + polish `65aaaad`, version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0020_ticket_admin_note`)
> **Rebuild:** admin_dashboard web bundle

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none (frontend-only version)                                  |
| Frontend builds       | admin_dashboard: 4 files changed +245/−7; 1 new component (`area-picker.tsx`) |
| alembic head          | `0020_ticket_admin_note` (unchanged)                          |

---

## What's New in This Branch

### Area picker by name (`65aaaad`)

- `area-picker.tsx` (new) — pick a geo area **BY NAME**: an area code ("TN-12") is an identifier, not a fact anybody holds in their head — an operator declaring an incident knows they mean Ariana, not that Ariana is the twelfth governorate. The search runs on the name and keeps the code as the value it submits.
- The search hits the existing catalog endpoint, which already matches French name, Arabic name and code — typing "Ariana", "أريانة" or "TN-12" all find the same row (debounced query via `useDebounced`).

### Wiring & polish

- `outage-manager.tsx` wired to the area picker for incident declaration.
- `metric-card.tsx` — new `compact` variant; used by the guardrails row on `/policies` (+1 line).
- Route `policies.tsx` polish.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_108` → **GREEN, exit 0** — 215 + 156 + 10 + 17 = **398 passed**, 0 failed.
- Version_107 on remotes untouched (`b76e818`).