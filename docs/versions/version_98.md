# Version 98 — Premium grid rendering fixes (z-index layering, transparent body, visible grid lines)

> **Base branch:** `version_97` (`61dfd0b`, pushed state)
> **Commits:** 3 — grid behind every component `d0853bd`, background on html only `e6e4cd4`, grid line opacity `3c2afbf`
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** customer_portal web bundle (styles.css + shell/routes)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none                                                          |
| Frontend builds       | customer_portal: `styles.css`, `portal-shell.tsx`, `__root.tsx`, `login.tsx`, `logout.tsx`, `signup.tsx` |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |

---

## What's New in This Branch

### Commit 1 — Paint the premium grid behind every component (`d0853bd`)

- `styles.css` — the `body::before` grid now sits at `z-index: -1`, between the page canvas and all app surfaces. Positioned `z-0` pseudo-elements paint above non-positioned content, so the grid lines were crossing cards and text; fixed by layering the grid under the canvas.
- Page wrappers (`portal-shell.tsx`, `__root.tsx`, `login.tsx`, `logout.tsx`, `signup.tsx`) made transparent so the canvas + grid show through.

### Commit 2 — Background on html only (`e6e4cd4`)

- `styles.css` — `body`'s own opaque background was painted as an in-flow block, above the negative-z grid, hiding it entirely. Body is now transparent so the grid on `body::before` shows through the canvas.

### Commit 3 — Grid line opacity (`3c2afbf`)

- `styles.css` — grid line opacity raised to a clearly visible level (fix 1 file, +4/−4).

---

## Validation

- `scripts/test_committed.ps1 -Ref version_98` → **GREEN, exit 0** — 187 + 145 + 10 + 17 = **359 passed**, 0 failed.
- Version_97 on remotes untouched (`61dfd0b`).