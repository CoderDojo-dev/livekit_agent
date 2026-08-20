# Version 99 — Hazy premium grid ambience (luminous core, cursor-following glow)

> **Base branch:** `version_98` (`74ef498`, pushed state)
> **Commits:** 1 — `b719b08` feat(ambience)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** customer_portal web bundle (grid-glow component, styles.css, __root)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none                                                          |
| Frontend builds       | customer_portal: `components/portal/grid-glow.tsx` (+68), `styles.css` (+81/−11), `routes/__root.tsx`, `scripts/verify-portal.sh` (+6) |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |

---

## What's New in This Branch

### Ambience — hazy premium grid with luminous core and cursor-following glow (`b719b08`)

- New `grid-glow.tsx` component — a hazy premium grid ambience: luminous core + a glow that follows the cursor across the portal canvas.
- `styles.css` (+81/−11) — the ambience styles: hazy grid treatment, luminous core, cursor-following glow layers.
- `__root.tsx` — ambience component mounted on the root layout.
- `verify-portal.sh` (+6) — new portal check covering the ambience surface.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_99` → **GREEN, exit 0** — 187 + 145 + 10 + 17 = **359 passed**, 0 failed.
- Version_98 on remotes untouched (`74ef498`).