# What we did — Batch 1 & Batch 2 (admin dashboard auth + navigation)

A human-readable recap of the last two implementation cookbooks, all applied locally (no push, no merge, no commit).

---

## Batch 1 — Admin authentication & session security

**Problem:** Anyone with a backend account could open the admin dashboard even if their role didn't allow it, sessions that were revoked or expired were not cleaned up, and the token used for API calls was stored in a way that could be exposed.

**What we changed (3 files):**

1. **`auth.server.ts`** — the heart of the fix:
   - After a user logs in, the dashboard now calls the backend (`GET /api/v1/auth/me`) to verify the account really exists and is allowed to use the admin dashboard.
   - Only **staff** accounts with role `conseiller`, `superviseur`, or `administrateur` get in.
   - If the backend says the session is revoked, invalid, or the role doesn't match → the session cookie is cleared and the user is redirected to `/login` (no redirect loops).
   - If the backend is **down** (network error/timeout/5xx) → the session cookie is kept and an error/retry screen is shown instead of silently logging the user out.
   - When a customer account (kind=client) tries to access, their backend token is also revoked server-side.
   - Logout always clears the local cookie, even if the backend is unreachable ("best-effort" revocation).
   - The token is **never sent to the browser** — the client only receives `{ sub, role, exp }`.

2. **`__root.tsx`** — just the wiring: it now uses the new session type from `auth.server.ts`. The redirect logic was NOT touched.

3. **`session.ts`** — one small type adjustment so the new session type works with the existing `hasRank` role-check function (approved deviation).

**Verified live (all passed):**
- Staff login works (dashboard opens, cookie kept).
- Revoked session → redirected to login, cookie cleared, no infinite loop.
- Customer account trying to log in → blocked, token revoked.
- Backend down → error screen (NOT a redirect), cookie preserved; after restart, everything works again with the same cookie.
- Role mismatch (cookie says conseiller, backend says administrateur) → kicked out, token revoked.
- Logout while backend is down → cookie still cleared, no error.

**Gates:** TypeScript 0 errors, lint 0 errors, build success, backend auth tests 12/12 passed.

---

## Batch 2 — Dashboard truthfulness & mobile navigation

**Problem:** The dashboard showed fake numbers and fake controls: hardcoded badges ("Tickets 42", "Callbacks 7"), a dead "Subscriptions" card, a search box and command-K shortcut that did nothing, and KPI cards that showed "0" while data was still loading (fabricated zeros). There was also no mobile navigation.

**What we changed (6 files):**

1. **`nav.ts`** — navigation source of truth:
   - Removed the hardcoded badge numbers (Tickets 42, Callbacks 7) and the badge system entirely (no fake counts, no replacement queries).
   - Updated page titles/subtitles to say only what the dashboard really does:
     - Overview: "Observed support KPIs, advisor availability and reported services."
     - Customers: "Search CRM customer records and open customer details."
     - Agents: "Review the agent catalog and observed activity."
     - Tickets: now says "Mirrored view, read-only" (we don't assign/resolve tickets).
     - Settings: now says "Audit, integrity and retention" (not general workspace management).
     - Advisors: now says "Registry, availability and capacity" (not performance monitoring).

2. **`app-sidebar.tsx`** — replaced with ONE shared navigation renderer:
   - Same component is used on desktop and mobile, so both show exactly the same menu.
   - Role-based filtering: `/policies` only appears for administrators.
   - Active page marked with `aria-current="page"` (accessibility).
   - Badge rendering removed.

3. **`app-topbar.tsx`** — top bar rebuilt:
   - **Mobile navigation**: a hamburger button (below large screens) opens a slide-in panel using the existing Sheet component. It has a proper accessible name, closes on Escape/overlay/close button, and closes automatically when you pick a destination.
   - Removed the dead controls: search box, Command-K hint, notifications bell.
   - Logout button still works exactly as in Batch 1.
   - Page title/subtitle from `nav.ts` is shown.

4. **`customers.tsx`** — Customers page:
   - Removed the placeholder "Subscriptions" card (it always showed "—").
   - KPI grid adjusted from 4 to 3 cards (Customers, Listed, Page).
   - Pagination behaviour (`keepPreviousData`) untouched.

5. **`agents.tsx`** — Agents page truthfulness:
   - While data is loading: shows 4 skeleton cards — **no zeroes**.
   - On error: shows an error/retry state — **no zeroes**.
   - On success: shows real counts derived from the actual data (Caller turns, Catalog personas, Observed personas, Unrecognized classes).
   - Removed the "Personas deployed" label (we don't deploy personas, we observe them).
   - Switching 7/14/30-day windows re-fetches and shows skeletons — no fake zero flash.

6. **`overview.tsx`** — Overview page wording:
   - "Service Inventory / Deployed services... Health is not monitored" → "Service Catalog / Services reported by system overview... Runtime health is not reported."
   - No queries or data mappings were changed.

**Verified live (all passed):**
- Admin sees `/policies` in the menu; a conseiller (non-admin) does not — same on desktop and mobile.
- Agents page streams 4 skeleton cards while loading; the backend really returns data (248 turns across 30 days).
- Customers page renders exactly 3 KPI cards, no Subscriptions placeholder.
- Overview says "Service Catalog" — no "Deployed services" text anywhere.
- Mobile trigger + desktop sidebar classes both present in the rendered HTML.
- Search checks: no `badge: 42/7`, no "Personas deployed", no "Deployed services", no Bell/Command/SearchInput left in the topbar.

**Gates:** TypeScript 0 errors, lint 0 errors (9 pre-existing warnings only), build success, `git diff --check` clean, backend auth tests 12/12 passed.

---

## Small adaptations made (documented, not invented)

- The cookbook code assumed a `PresenceDot` prop (`status`) that doesn't exist in our codebase — used our real prop (`live`) which renders the same green online dot.
- A `Link` type cast was kept because our router's typed routes require it (same as before the patch).
- Prettier re-formatted 3 files to match our project's formatting rules (cosmetic only).

## Deliverables

- `patch-v89-admin-auth-session-batch1-RESULTS.md` (Batch 1)
- `patch-v89-batch2-dashboard-truthfulness-mobile-nav-RESULTS.md` (Batch 2)

Everything is local-only: no commits, no push, no merge. Dev server runs at http://localhost:8080 if you want to look.