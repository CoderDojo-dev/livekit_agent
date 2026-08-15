# Version 91 — Admin dashboard: auth session hardening, truthfulness + mobile nav, account security + audit pagination, backend env overrides

> **Base branch:** `version_90` (`f6063f6`)
> **Commits:** 1 (Batches 1-3 + supporting extensions + 3 docs)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none (head stays `0017_notification_failure_reason`)
> **Rebuild:** required — business-api (backend auth env overrides) + admin_dashboard web bundle

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| livekit-server        | `v1.8.4` (unchanged)                                          |
| Backend service code  | business-api: `rate_limit.py` + `portal_auth.py` (env overrides only) |
| Image rebuild         | **business-api** (Python source changed); admin_dashboard rebuilt on deploy |
| alembic head          | `0017_notification_failure_reason` (unchanged)                |
| Frontend              | admin_dashboard: 13 files (12 edits + 1 new); customer_portal untouched |
| New env knobs         | `PORTAL_RATE_LIMIT_ATTEMPTS` (20), `PORTAL_MAX_FAILED_ATTEMPTS` (5), `PORTAL_LOCKOUT_MINUTES` (15) — defaults unchanged, for local test environments |

---

## What's New in This Branch

Three applied cookbook batches (admin dashboard) plus two supporting extensions.
Every change was verified live against the running system before commit.

### Batch 1 — Admin authentication & session security

**Problem:** anyone with a backend account could open the dashboard even if their
role didn't allow it; revoked/expired sessions were not cleaned up; the API token
was stored in a way that could be exposed.

- **`auth.server.ts` (heart of the fix):** after login the dashboard calls
  `GET /api/v1/auth/me` to verify the account really exists and is staff
  (`conseiller`/`superviseur`/`administrateur`). Revoked/invalid session or role
  mismatch → cookie cleared + redirect to `/login` (no redirect loops). Backend
  **down** (network/timeout/5xx) → cookie **kept** + error/retry screen (never a
  silent logout). A customer account (`kind=client`) trying to log in gets its
  backend token revoked. Logout always clears the local cookie (best-effort
  revocation).
- **Token never reaches the browser** — the client only receives
  `SessionView { sub, role, exp }`. Strict runtime validation of `/login` and
  `/me` payloads (`parseLoginResponse`/`parseMeResponse`, per-field checks) +
  typed `MalformedUpstreamResponse` (502).
- **`session.ts`:** `hasRank` accepts `Pick<AdminSession, "role">` (approved
  deviation so the new session view works with the existing role-check).
- **`__root.tsx`:** wiring only — redirect logic untouched.

### Batch 2 — Dashboard truthfulness & mobile navigation

**Problem:** fake numbers and fake controls — hardcoded badges ("Tickets 42",
"Callbacks 7"), a dead "Subscriptions" card, a search box and Command-K shortcut
that did nothing, KPI cards showing fabricated zeros while loading, and no mobile
navigation.

- **`nav.ts`** — removed the badge system entirely (no fake counts, no
  replacement queries). Titles/subtitles now say only what the dashboard really
  does: Tickets = "Mirrored view, read-only", Settings = "Audit, integrity and
  retention", Advisors = "Registry, availability and capacity", etc.
- **`app-sidebar.tsx`** — ONE shared `SidebarContent` for desktop and mobile;
  `/policies` only for administrators; `aria-current="page"` active marker;
  badge rendering removed.
- **`app-topbar.tsx`** — rebuilt: mobile hamburger opens a slide-in Sheet panel
  (accessible name, Escape/overlay/close, auto-closes on destination pick);
  removed the dead search box, Command-K hint and notifications bell; page
  title/subtitle from `nav.ts`; logout unchanged.
- **`customers.tsx`** — removed the placeholder "Subscriptions" card; KPI grid
  4 → 3 (Customers, Listed, Page); `keepPreviousData` untouched.
- **`agents.tsx`** — skeletons while loading (**no zeroes**), error/retry state,
  real counts from actual data (Caller turns, Catalog personas, Observed
  personas, Unrecognized classes); removed "Personas deployed" (we observe, not
  deploy); window switches re-fetch with skeletons — no fake zero flash.
- **`overview.tsx`** — wording only: "Service Inventory / Health is not
  monitored" → "Service Catalog / Runtime health is not reported".

### Batch 3 — Administration & account security

- **`settings.tsx` (full rewrite):**
  - `AccountSecurityPanel` (all staff roles): change password with the **same
    local validation as the backend** (empty / < 10 chars / same as current /
    confirmation mismatch); revoke-all sessions with Modal confirm; `onSuccess` →
    `router.invalidate()` then navigate to `/login`.
  - `AuditLedgerTable` on `useInfiniteQuery` cursor pagination
    (`initialPageParam: null`, `next_before_seq`, filter swap resets the cursor,
    `TableErrorRow` on first-load failure, pages preserved on later-page
    failure, footer "{n} entries loaded" + "Load older").
  - Admin-only controls behind `hasRank(session, "administrateur")`; non-admins
    get an EmptyState, not an error.
- **`auth.server.ts`** — `revokeAllSessions` createServerFn POST with
  `RevokeAllSessionsResult { sessions_revoked }`. **Cookie cleared only after a
  shape-validated success** — there is no cookie clear in a `finally`, so
  401/502/503 paths leave the session intact. Malformed response →
  `ApiError(502, "invalid revoke-all response")`.
- **`__root.tsx`** — `NotFoundComponent` (404, "Go to overview", SearchX icon)
  + `ErrorComponent` (AlertTriangle, retry) rewritten in Nexus styling;
  `console.error`/`reportLovableError` moved into `useEffect` (no render-body
  side effects). **Bonus fix:** kills the pre-existing Settings hydration
  warning (session now comes from the root route context instead of a
  `TableSkeleton` under `PageSection`).
- **`app-sidebar.tsx`** — `ADMIN_ONLY_HREFS = new Set(["/policies", "/reference"])`
  (one line, applies to desktop AND mobile). Reference stays **server-guarded**:
  the sidebar only hides it; the endpoints enforce `administrateur` at the API.

### Supporting extensions

- **`lib/api/errors.ts`** — `toApiError()` reconstructs an `ApiError` from a real
  instance **or a serialized plain Error** (TanStack Start RPC preserves only
  `message`; regex `^business-api (\d{3}) on (.+?): …`). `isApiError`/
  `isUnauthenticated`/`isForbidden` rebuilt on it; `loginMessage()` gives
  human-readable copy for the sign-in page (never leaks a stack trace).
  `customer-detail.tsx` migrated to `toApiError()`.
- **Backend env overrides** (local test environments only; defaults unchanged):
  `rate_limit.py` `max_attempts()` reads `PORTAL_RATE_LIMIT_ATTEMPTS` (default
  20); `portal_auth.py` `max_failed_attempts()`/`lockout_minutes()` read
  `PORTAL_MAX_FAILED_ATTEMPTS` (default 5) / `PORTAL_LOCKOUT_MINUTES` (default
  15). Lets endpoints be exercised without tripping the throttle/lockout.

---

## Validation

- `tsc --noEmit` (admin_dashboard): **0 errors**
- `npm run lint`: **0 errors, 9 warnings** (pre-existing baseline, unchanged)
- `npm run build`: **success** (vite client + SSR + nitro)
- `git diff --check`: clean
- `ruff check` on both backend files: **All checks passed!**
- Full chain `test_committed.ps1 -Ref version_91`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)
- Backend auth tests: `test_auth_http.py` + `test_auth_rate_limit.py` → **15 passed**

### Live verification highlights

| Check | Result |
|---|---|
| Staff login | dashboard opens, cookie kept |
| Revoked session | → login, cookie cleared, no infinite loop |
| Customer account login | blocked, token revoked server-side |
| Backend down | error screen (NOT redirect), cookie preserved |
| Role mismatch (cookie vs backend) | kicked out, token revoked |
| Logout while backend down | cookie still cleared, no error |
| Revoke-all sessions | `200 {sessions_revoked: 51}`, both devices invalidated, `auth_sessions_revoked` ledger entry with actor block + `entity_reference: portal_accounts:<uuid>` |
| Password change lifecycle | wrong current 401 · < 10 chars 400 · same as current 400 · valid 200 `{changed: true, sessions_revoked: 6}` · old token immediately 401 · revert OK |
| Audit pagination | 50 + 43 = 93 entries, strictly descending, no duplicate seqs, in-page AND cross-page hash linkage true, filter `auth_sessions_revoked` + `before_seq` correct, no page-edge false positive |
| SSR role matrix | conseiller/superviseur/administrateur on `/overview` sidebar + `/settings` (temp accounts deleted after; DB restored to 3 accounts) |

---

## Out of scope / notes

- No browser E2E tooling available — browser behaviors verified via SSR HTML +
  live business-api HTTP + code inspection (stated in the batch-3 report).
- `ADMIN_ONLY_HREFS` adds `/reference` to the admin-only set (one-line change
  from the cookbook's `/policies`-only baseline).
- `PROJECT_RECAP.md`, `PHASE1_CODEBASE_COMPREHENSION.md` and
  `BATCH1-BATCH2-HUMAN-RECAP.md` committed alongside the code as requested
  deliverables.