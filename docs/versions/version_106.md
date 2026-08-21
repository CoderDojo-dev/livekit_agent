# Version 106 — Admin console interface language (i18n en/fr/ar + RTL), calls route rebuild

> **Base branch:** `version_105` (`0d343f8`, pushed state)
> **Commits:** 2 — console i18n `7b5226e`, version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0020_ticket_admin_note`)
> **Rebuild:** admin_dashboard web bundle (i18n, locale preference, language toggle)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none (frontend-only version)                                  |
| Frontend builds       | admin_dashboard: 10 files changed +256/−188; 2 new files (`i18n.ts`, `language-toggle.tsx`) |
| alembic head          | `0020_ticket_admin_note` (unchanged)                          |

---

## What's New in This Branch

### Interface language for the console (`7b5226e`)

- `lib/nexus/i18n.ts` (new) — translates the **SHELL**: navigation, page titles and subtitles, and the vocabulary that repeats on every screen (search, save, cancel, pagination, empty and error states). Locales: **en / fr / ar**.
- **Scope, stated honestly:** page body copy — the governance prose on `/policies`, the provenance notes, the KPI context lines — remains English for now. Those strings are precise, legally-flavoured and frequently argued over; a rough translation of "thresholds are enforced from POLICY_* environment variables" would be worse than leaving it in the language it was written in.
- **Graceful partial translation:** `t()` falls back to English per key, so a partially filled dictionary renders a partially translated page rather than a page full of missing-key markers. The mechanism carries the remaining strings the moment a translation exists.
- **Arabic RTL:** `ar` sets `dir="rtl"` on `<html>`; layout uses CSS logical properties (start/end rather than left/right) so sidebar, paddings and alignment mirror without a second stylesheet.
- `preferences.ts` — new `locale: ConsoleLocale` ("en" | "fr" | "ar") preference, default `"en"`. The type is duplicated rather than imported from `i18n.ts` because that module imports THIS one for the store — a cycle would break the pre-paint script's key list; `i18n.ts` re-exports the same union.
- `language-toggle.tsx` (new) — shell control to switch interface language.

### Polish

- `calls.tsx` rebuilt (+342/−), `pager.tsx`, `metric-card.tsx`, `blocks.tsx`, `primitives.tsx`, `app-sidebar.tsx`, `app-topbar.tsx`, `theme-toggle.tsx`, `styles.css`.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_106` → **GREEN, exit 0** — 215 + 156 + 10 + 17 = **398 passed**, 0 failed.
- Version_105 on remotes untouched (`0d343f8`).