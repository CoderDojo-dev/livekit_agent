# Version 97 — Cookbooks 17-20 (billing crash guard, language precedence, assistant two-column, branding), seamless cookie/preferences migration, error-handling regression tests

> **Base branch:** `version_96` (`fa220ab`, pushed state)
> **Commits:** 4 — cookbooks 17-20 + verify-portal 14-18 `54605e7`, cookie/preferences migration `46ca168`, error handling regression tests `2ea3c0e`, cookbook specs `eaf25e2`
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** customer_portal web bundle (billing/assistant/activity/preferences/branding), agent-worker (`language_policy.py`, server.py)
> **New CI checks:** `verify-portal.sh` gains checks 14-18 (migration literals, new routes, branding assets)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | agent-worker: `config/language_policy.py` (+79), `server.py` (+22) — session-language precedence; business-api untouched |
| Frontend builds       | customer_portal: billing, assistant, activity, preferences, profile, __root, shell, primitives, data, styles.css (+122), branding assets (favicons, apple-touch-icon) |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |
| New CI checks         | `verify-portal.sh` checks 14-18 (cookie migration literals excluded from banned list, new routes, branding/favicon presence) |

---

## What's New in This Branch

### Commit 1 — Cookbooks 17-20 applied (`54605e7`)

- **Cookbook 17 — billing crash guard:** `currencyOrDefault` with TND fallback + turn-count rendering helpers (`format.ts`, `conversation.ts`, `activity.tsx`); billing page guarded against missing/unknown currency.
- **Cookbook 18 — language precedence (French default):** agent-worker `language_policy.py` — precedence `explicit > saved preference > default`, French fallback; `server.py` wired; `test_language_policy.py` (+65).
- **Cookbook 19 — assistant two-column:** animated `0fr-1fr` grid scene, transcript-only scroller, `h-screen` no-scroll shell (`assistant.tsx` +122, `portal-shell.tsx`, `portal-rail.tsx`).
- **Cookbook 20 — branding/grid/light-mode/buttons/activity:** brand copy (`copy.ts`, `data.tsx`), `pageTitle` route heads, `portal_preferences` + `portal_session` storage keys, light-theme token block (`styles.css` +122), premium grid, favicon set (svg/ico/apple-touch-icon), focus-ring token, button motion, activity turn-density bars.
- **Tests:** `conversation.test.ts` (+43), `format.test.ts` (+16).

### Commit 2 — Seamless cookie & preferences migration (`46ca168`)

- Session cookie renamed; `session.server.ts` reads the legacy `nexus_portal_session` cookie as fallback so the rename logs **nobody out**; logout clears both cookie names so the legacy cookie cannot resurrect a session; pre-paint theme script falls back to the legacy preferences key; `verify-portal.sh` check 14 excludes both migration literals; `session.server.test.ts` (+92) migration regression tests.

### Commit 3 — Error-handling regression tests + polish (`2ea3c0e`)

- `errors.test.ts` (+60/−18) extended coverage; `errors.ts` newline/copy polish.

### Commit 4 — Cookbook specs (`eaf25e2`)

- `features_to_apply/client_portal_cookbooks/cookbooks-v97/`: `00-REVIEW-OF-version_96.md`, `17-billing-crash-and-turns-rendering.md`, `18-language-precedence-french-default.md`, `19-assistant-two-column-and-noscroll.md`, `20-branding-grid-lightmode-buttons-activity.md`.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_97` → **GREEN, exit 0** — 187 + 145 + 10 + 17 = **359 passed**, 0 failed.
- Version_96 on remotes untouched (`fa220ab`).