# Version 102 — Admin dashboard UI/UX phase 1 (brand system, motion, count strip, pager, shared primitives)

> **Base branch:** `version_101` (`60591fe`, pushed state)
> **Commits:** 2 — main UI/UX work `2c14cba`, version doc
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** admin_dashboard web bundle (new `framer-motion` dependency, brand system, shared primitives)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none (frontend-only version)                                  |
| Frontend builds       | admin_dashboard: package.json gains **framer-motion ^13.1.1**, package-lock updated; 36 files changed +3347/−1755; 12 new files |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |

---

## What's New in This Branch

### Brand system (`2c14cba`)

- `brand-mark.tsx` + `lib/nexus/brand.ts` — brand mark and brand tokens.
- `lib/nexus/motion-tokens.ts` + `components/nexus/motion.tsx` — motion tokens and motion wrapper (framer-motion-backed).
- **New dependency:** `framer-motion` `^13.1.1` (admin_dashboard only).

### Count strip & nav counts

- `components/nexus/count-strip.tsx` — strip of live counts.
- `lib/api/nav-counts.server.ts` — nav counts server loader.
- `lib/nexus/nav.ts`, `query-keys.ts` — nav wiring updated.

### Pager & pagination

- `lib/nexus/paginate.ts` + `paginate.test.ts` — honest pagination util with tests.
- `components/nexus/pager.tsx` — pager component.
- `hooks/use-adaptive-page-size.ts` — page size adapts to viewport.
- `hooks/use-overflow-x.ts` — horizontal overflow detection hook.

### Shared primitives & polish

- `blocks.tsx`, `primitives.tsx`, `modal.tsx`, `states.tsx`, `app-sidebar.tsx`, `app-topbar.tsx` — rebuilt with shared primitives and consistent motion.
- All routes rebuilt (`advisors`, `agents`, `analytics`, `audit`, `availability`, `callbacks`, `calls`, `customers`, `decisions`, `escalations`, `knowledge`, `login`, `notifications`, `overview`, `policies`, `reference`, `settings`, `tickets`), `__root.tsx`, `styles.css` (+161/−) rework.
- `audit-page.tsx`/`audit-page.test.tsx`, `escalations-page.tsx`, `agent-activity-sparkline.test.tsx`, `agent-view.test.ts`, `agents.test.tsx` updated.

### Docs

- `features_to_apply/admin_dashboard_uiux/PHASE1_UIUX_AUDIT.md` (29 KB audit) + `UIUX_IMPLEMENTATION_RESULTS.md` (12 KB results).

---

## Validation

- `scripts/test_committed.ps1 -Ref version_102` → **GREEN, exit 0** — 204 + 145 + 10 + 17 = **376 passed**, 0 failed.
- Version_101 on remotes untouched (`60591fe`).