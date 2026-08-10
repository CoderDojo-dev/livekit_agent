# Version 84 — P0-1 real authentication, P0-2 fail-closed default role, ORB display quality, customer portal identity

> **Base branch:** `version_83` (`7f67f08`)
> **Commits:** 1 (features lot)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none (`git diff pyproject.toml` empty)
> **Migration:** `0016_portal_identity` (applied, head confirmed)

---

## Containers & SDK

| Item               | Change                          |
|--------------------|---------------------------------|
| New containers     | None                            |
| livekit-agents SDK | `1.6.5` (unchanged)             |
| livekit-server     | `v1.8.4` (unchanged)            |
| Docker Compose     | Unchanged                       |
| Alembic            | **0016_portal_identity** — new `auth.portal_accounts` / `auth.portal_sessions` (applied, head in DB) |
| agent-worker       | rebuilt + restarted (machine-identity clients `routing_client.py`/`callback_client.py` → `internal_headers()`) |
| business-api       | rebuilt (auth layer)            |

---

## 1. P0-1 — Real Authentication (one identity layer, both frontends)

**The vulnerability closed:** before P0-1, `security.py` resolved a caller's role as
`role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")` — **any anonymous
request arrived as a full administrator**. P0-1 deletes that expression; role now comes **only**
from a principal business-api resolved itself. Unauthenticated = **401**, authenticated-but-
outranked = **403**. There is no third outcome and no env var that produces one.

- **Persistence**: `models/portal_identity.py` (client row attached to `crm.customers`, staff row
  with one of the three backend roles) + migration `0016_portal_identity` on top of
  `0015_outage_description_area_code`; exported in `models/__init__.py`.
- **Identity layer** (`infrastructure/auth/`): `passwords.py` (argon2id), `tokens.py` (opaque
  64-hex tokens, only digests stored), `cin.py` (CIN last-4 factor), `rate_limit.py`,
  `principal.py` (staff bearer / client bearer / machine key resolution; empty/forged machine
  key → 401 — `if x_api_key and expected and hmac.compare_digest(...)`).
- **`security.py` replaced**: contract preserved, `require_role` now consumes the resolved
  principal. `portal_auth.py` (login/logout/me) + `seed_admin.py` (idempotent admin seed).
- **`main.py`**: auth routes, `/auth/me/profile`, `/auth/me`; CORS pinned to
  `http://localhost:5173`, `Access-Control-Allow-Headers` has **no X-Role**.
- **agent-worker machine identity**: `routing_client.py` + `callback_client.py` send
  `internal_headers()` (`X-API-Key: dev-key-123`, **no X-Role**) — the worker is pinned to the
  `conseiller` rank by the shared key, never by an asserted role.
- **Frontends**: admin `session.ts`/`auth.server.ts`/`business-api.ts` rewired to bearer
  sessions; customer portal `login.tsx`/`signup.tsx` + `_portal.tsx` gate + `lib/api/` session,
  me, middleware, errors clients.

## 2. P0-2 — Fail-Closed Default Role (cleanup that makes the fix legible)

The live hole was shut by P0-1 (proved: anonymous `/customers` 401, forged `X-Role` 401).
P0-2 removes every remaining path to a role without authenticating:

- `.env.example`: `BUSINESS_API_DEFAULT_ROLE=administrateur` block deleted, prohibition comment
  added; `Frontend/admin_dashboard/.env.example`: 3 dead `ADMIN_*` lines deleted (kept
  `ADMIN_SESSION_SECRET`/`ADMIN_SESSION_TTL`); `config.ts` accessors deleted.
- `deploy/gateway/nginx.conf`: `proxy_set_header X-Role $http_x_role;` removed (comment kept).
- `security.py` docstring reworded (authorised; no code change), `answers.md` stale row deleted.
- **Guard**: `test_no_default_role.py` (3 tests) added **before** the deletions — passes on the
  already-clean tree, so the guard can't be satisfied by the cleanup itself. `verify_p0_2.sh`
  (9 checks): comment-filtered grep so prose/`_FORBIDDEN` don't self-trip, `-X POST` on the
  POST-only retention route (405-before-auth fixed).

## 3. ORB display quality (customer_portal)

- `orb-renderer.ts`: closest-approach tracking → coverage feather ≈1.5 px; march budget
  72 → 96; lighting gate `cov > 0.004` (edge pixels shade at `pClosest`); alpha
  `clamp(max(cov, halo*5), 0, 1)`; `FRAGMENT_BUDGET = 640×640`, `effectiveDpr()` capped at 3,
  recomputed on `resize()`.
- `orb.tsx`: `webglcontextlost` listener → `preventDefault()` + destroy + CSS radial-gradient
  fallback (cleanup removes the listener).

---

## Validation

- business-api: **58/58 PASS** (55 baseline + 3 guard; 5 new `test_auth_*` files + `api_client`
  fixture bound to the rolled-back transaction)
- Full chain `test_committed.ps1 -Ref version_84`: **170/170 PASS**
  (business-api 58, agent-worker 85, notification 10, policy 17)
- `verify_p0_1.sh` **20/20 live** (incl. case 20: image with forced-empty `INTERNAL_API_KEY`
  rejects both empty and forged keys); `prove_p0_1_data_integrity.sql` **9/9**; voice-flow
  **6/6** inside the worker container (`/advisors/on-call` 200, `/callbacks/slots` 200,
  `/advisors/claim` 200, `/release` 200, `/tickets` 403)
- `verify_p0_2.sh` green (decision-log adaptations: comment filter, `-X POST` check 9)
- Admin + portal `tsc --noEmit` → **0**; lint 0 errors (pre-existing warnings unchanged);
  builds OK
- DB: head `0016_portal_identity`, portal tables present, no cleartext `password` column anywhere
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`

---

## Out of scope (unchanged)

- Pre-existing ruff baseline (main.py 7, repo-wide 147 — recorded, not fixed)
- All items previously listed as out of scope in v79–v83.