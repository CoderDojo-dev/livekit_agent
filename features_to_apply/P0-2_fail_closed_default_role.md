# P0-2 — Fail-Closed Default Role

**Branch:** `version_83`
**Baseline:** P0-1 applied locally (alembic head `0016_portal_identity`), `verify_p0_1.sh` 20/20.
**Scope:** remove every path by which a role can be obtained without authenticating.
**Size:** 3 edited files, 1 new file, 2 new tests, 1 new script. No backend logic changes.

---

## §1 What P0-2 actually is — and the honest statement of residual risk

Read this section before anything else, because it changes how you should feel about the work.

**The live vulnerability is already closed.** P0-1 deleted the expression

```python
role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
```

from `apps/business-api/src/business_api/security.py`. The proof already exists and is already
green: `verify_p0_1.sh` **case 2** (anonymous `/customers` → 401) and **case 3** (forged
`X-Role: administrateur` → 401). If a default role were still honoured, both of those would have
returned **200**. They returned 401. The hole is shut, and it was shut by the previous patch.

So P0-2 is **not** a vulnerability fix. It is the cleanup that makes the fix *legible and
permanent*. That distinction matters because three things are still true:

| Residual item | Live risk today | Why it still must go |
| --- | --- | --- |
| `BUSINESS_API_DEFAULT_ROLE=administrateur` in `.env.example` | **None** — no code reads it | It documents a granting mechanism to every future reader. Someone will wire it back. |
| `proxy_set_header X-Role $http_x_role;` in `deploy/gateway/nginx.conf` | **None** — no nginx container runs | It is an edge component forwarding a *client-controlled* role header. If that deploy target is ever revived, the gateway becomes an accomplice the moment anyone re-reads the header. |
| `adminRole: () => optional("ADMIN_ROLE", "administrateur")` in the admin frontend `config.ts` | **None** — provably unread (see §6.1) | It is a **second** default-role surface, in a second language, that still literally says "Backend role granted on login". |

All three are dormant. None is exploitable. **Every one of them is a loaded gun with the safety
on**, and the entire point of a fail-closed posture is that you do not keep loaded guns in the
drawer because the safety is currently engaged.

> **I will not overstate this patch.** If you want a one-line summary for the commit: *"P0-2
> removes the dormant role-default surfaces P0-1 made unreachable, and adds the regression guard
> that keeps them unreachable."* It is a hygiene-and-durability patch. It is short on purpose.

### 1.1 The one thing here that is genuinely new

Everything above is deletion. The new *capability* is §8.2: a test that fails if anyone ever
reintroduces an environment-sourced role default anywhere in the business-api source tree.

Without it, P0-2 is a one-time tidy that decays. With it, the property is enforced by CI forever.
That test — not the deletions — is the reason this patch is worth a document.

---

## §2 Coverage disclosure — what I read, and what I did not

Stated up front, per rule 1.7. **Do not treat an unread file as clean.**

**Read at `version_83`, byte-exact, for this patch:**

| File | Evidence |
| --- | --- |
| `Makefile` | blob `26ea4077` |
| `.github/workflows/ci.yml` | blob `a62ea96c` |
| `deploy/README.md` | blob `f4a36dcc` |
| `deploy/gateway/nginx.conf` | blob `5968cfbb` |
| `deploy/secrets/.env.example` | blob `0a70f6cb` |
| `deploy/helm/telecom-agent/values.yaml` | blob `d8817b96` |
| `Frontend/admin_dashboard/src/lib/api/config.ts` | blob `16652bc4` |
| `infra/docker-compose/docker-compose.yml` | blob `0133a820` (earlier batch) |
| `infra/docker-compose/docker-compose.apps.yml` | blob `6b3cb641` (earlier batch) |

**Directory listings obtained:** `deploy/`, `deploy/gateway/`, `deploy/helm/`,
`deploy/helm/telecom-agent/`, `deploy/secrets/`, `infra/helm/`, `Frontend/admin_dashboard/`.

**NOT read — you must check these yourself in STEP 0.3, they are not certified clean:**

- `infra/helm/telecom-platform/**` (exists; contents unread)
- `deploy/helm/telecom-agent/templates/**`
- `deploy/backup/`, `deploy/otel/`, `deploy/postgres/`
- `deploy/gateway/docker-compose.gateway.yml` (379 B, unread)
- `infra/ci-cd/**`
- `docs/**`, `answers.md`, `commands.md`
- `Frontend/admin_dashboard/.env.example` (exists, 1448 B, **contents unread**)

The single `git grep` in STEP 0.3 covers all of them at once. That is why the sweep is a command
you run, not a table I assert.

### 2.1 A correction to my own earlier speculation

In review I raised the worry that the admin form login might be broken, because `config.ts` still
`required()`s `ADMIN_EMAIL`/`ADMIN_PASSWORD` and the admin app `.env` carries stale placeholders
(`admin@nexus.io` / `change-me`) that do not match the seeded backend account.

**That worry was unfounded, and I withdraw it.** I have now read the P0-1 replacement body of
`auth.server.ts` (cookbook §10.2). Its imports are `serverConfig`, `ApiError`, the
`session.server` helpers, and `ROLE_RANK`. It calls `serverConfig` for exactly two things:
`businessApiUrl()` and `requestTimeoutMs()`. **It never reads `adminEmail`, `adminPassword`, or
`adminRole`.** Login posts the submitted credentials straight to `/api/v1/auth/login` and trusts
the backend's answer.

So the stale placeholders are harmless *because nothing reads them* — which is exactly what the
implementer reported, and they were right. The consequence is not a bug; it is that three config
entries are now dead weight, one of which hands out `administrateur`. That is what §6 removes.

---

## §3 The sweep — `BUSINESS_API_DEFAULT_ROLE`

Evidence-backed status of every location I read:

| Location | Contains it? |
| --- | --- |
| `.env.example` §22 | **YES** — the one line to delete (§4) |
| `apps/business-api/.../security.py` | No — expression deleted by P0-1 |
| `infra/docker-compose/docker-compose.apps.yml` (all 15 services) | No |
| `infra/docker-compose/docker-compose.yml` | No |
| `Makefile` | No |
| `.github/workflows/ci.yml` | No |
| `deploy/README.md` | No (documents `POLICY_*` only) |
| `deploy/secrets/.env.example` | No — it is a pointer file with zero variables |
| `deploy/helm/telecom-agent/values.yaml` | No — its `env:` block holds only `CONNECTOR_MODE: mock` |

Separately, `X-Role` as a *forwarded header* survives in exactly one infrastructure file:
`deploy/gateway/nginx.conf` (§5). The only remaining **front-app source** that still sends it is
`apps/supervisor-dashboard/src/api.ts`, which is out of scope here and tracked in §16.3.

---

## §0 Pre-flight gates

Run all of these. Every one is a **location predicate or a state check — never a count.**

### 0.1 Baseline

```bash
git rev-parse --abbrev-ref HEAD          # expect: version_83
cd packages/persistence && alembic current   # expect: 0016_portal_identity (head)
```

### 0.2 P0-1 is green before you touch anything

```bash
bash scripts/verify_p0_1.sh              # expect: 20/20
python -m pytest apps/business-api/tests -q   # expect: all passed, no failures
```

> If `verify_p0_1.sh` is not 20/20, **stop**. P0-2 is a cleanup layered on P0-1; applying it over a
> broken P0-1 will produce a confusing failure that looks like P0-2's fault.

### 0.3 The sweep — this is the gate that defines the patch

```bash
# A. Every occurrence in the repo, excluding the cookbook folder (historical docs).
git grep -n "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply'

# B. Every X-Role occurrence under deployment/infra trees.
git grep -n "X-Role\|X_ROLE\|x-role" -- deploy/ infra/ .github/

# C. Any other environment-sourced role default, phrased differently.
git grep -nE "DEFAULT_ROLE|default_role" -- . ':!features_to_apply'
```

**Expected before the patch:**

- **A** → hits in `.env.example` only.
- **B** → hits in `deploy/gateway/nginx.conf` only.
- **C** → hits in `.env.example` only.

**If any command returns a location not listed above — STOP and report it.** That is a surface I
never read, and the fix belongs in this patch, not in a later one. Do not silently extend the
patch to cover it; tell me what you found first, because an unexpected hit in `infra/helm/` or
`infra/ci-cd/` may mean a deploy target actively sets the variable, which is a different and more
serious finding than dead documentation.

### 0.4 The consumer check that gates §6

```bash
git grep -n "adminEmail\|adminPassword\|adminRole" -- Frontend/
```

**Expected:** exactly three hits, all of them the *definitions* in
`Frontend/admin_dashboard/src/lib/api/config.ts`.

**If there is a fourth hit anywhere — a consumer — STOP.** §6 is then wrong and must not be
applied as written. Report the consumer. (I read the post-P0-1 `auth.server.ts` and it does not
consume them, but `auth.server.ts` is not the whole app, and I did not read all 21 other
`*.server.ts` files for this specific symbol. This grep is the authority, not my reading.)

### 0.5 Lint baseline — and a warning about what "baseline" means

```bash
ruff check apps/business-api/src/business_api/main.py | tail -1
```

Expect the post-P0-1 baseline (the B904 sites were closed with `from None`).

> **Do not read "baseline restored" as "CI is green."** `.github/workflows/ci.yml` runs
> `ruff check .` **repo-wide** in its `lint` job. If `main.py` still reports errors and
> `pyproject.toml` has no per-file ignore covering them, **that job is currently failing on
> `main`.** I have not read the full ruff config, so I am not asserting it is red — I am telling
> you the invariant "no *new* lint" does not imply "lint passes." Verify once:
>
> ```bash
> ruff check . 2>&1 | tail -3       # the exact thing CI runs
> ```
>
> Whatever this prints, **do not fix it in P0-2.** Getting `ruff check .` to zero is P1-2/P1-3
> work with its own blast radius. Record the number and move on.

---

## §4 Change 1 — delete the variable from `.env.example`

**File:** `.env.example` (repository root)

### 4.1 Why this edit is specified by location, not by a byte-exact anchor

P0-1's Edit B rewrote this block. It replaced the bare variable with the variable *plus* an
annotation reading, in substance, that P0-1 removed `X-Role` and this variable from the
authentication path, that `BUSINESS_API_DEFAULT_ROLE` is no longer read by any code, that it is
kept only so existing `.env` files stay valid, and *"Delete it whenever convenient."*

**I do not hold that annotation byte-exact.** I will therefore not fabricate an `oldStr` for it.
This edit is specified as *locate → delete → verify final state*. Open the file and do it by hand.
That is slower and it is correct; a guessed anchor would fail to apply and waste more time than
the manual edit costs.

### 4.2 The edit

1. Open `.env.example`.
2. Find section **§22**. It contains the line `BUSINESS_API_DEFAULT_ROLE=administrateur` and,
   immediately above it, the P0-1 annotation comment block describing it as no-longer-read.
3. **Delete the variable line and its annotation comment block.**
4. If §22 becomes empty as a result, delete the now-empty `# §22 ...` heading too. If §22 contains
   other unrelated variables, **leave them exactly as they are.**
5. **Do not touch §22b** (the portal-auth block P0-1 added: `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
   `ADMIN_ROLE`, `ADMIN_SESSION_SECRET`, `PORTAL_SESSION_SECRET`, the TTLs). Those are live and
   required — see §6.4 for exactly why they stay.

### 4.3 Replace the annotation with a prohibition

Deleting the line silently loses the *lesson*. Add this to §3 of `.env.example` (the
service-to-service auth section, next to `INTERNAL_API_KEY`), so the next person who wants a
convenient dev shortcut reads the reason it does not exist:

```bash
# ---------------------------------------------------------------------------
# There is deliberately NO variable that grants a role without authenticating.
#
# Until P0-1 this file carried BUSINESS_API_DEFAULT_ROLE=administrateur, and
# security.py resolved a caller's role as:
#     role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")
# Any anonymous request therefore arrived as a full administrator.
#
# Roles now come only from a principal business-api itself resolved:
#   - staff/client : bearer token, revalidated against auth.portal_sessions
#   - machine      : INTERNAL_API_KEY, pinned to the conseiller rank
# Unauthenticated is 401. Authenticated-but-outranked is 403. There is no third
# outcome, and there is no environment variable that produces one.
#
# apps/business-api/tests/test_no_default_role.py fails the build if this is
# ever reintroduced. Do not add it back.
# ---------------------------------------------------------------------------
```

### 4.4 Verify

```bash
git grep -n "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply'   # expect: no output
git diff --stat -- .env.example                                      # expect: only .env.example
```

> **Your local gitignored `.env` is not affected and needs no edit.** If it happens to contain
> `BUSINESS_API_DEFAULT_ROLE`, the variable is read by nothing, so removing it is optional
> hygiene. Removing it will not change behaviour. **Do not remove `ADMIN_*` or the two session
> secrets from your local `.env`** — those are live.

---

## §5 Change 2 — stop the gateway forwarding a client-controlled role

**File:** `deploy/gateway/nginx.conf`

### 5.1 The current state, byte-exact

```nginx
    # Back-office API for the supervisor dashboard (RBAC enforced in the app)
    location /api/ {
      proxy_pass http://business_api/api/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Role $http_x_role;
    }
```

`$http_x_role` is *the client's own `X-Role` request header*. This block takes a header the
browser controls and re-asserts it to business-api as though the edge had validated it. It never
validated anything.

**This is inert today** — there is no nginx container in either compose file, so no request has
ever traversed this config in the running system, and business-api no longer reads the header
anyway. It is a two-lock coincidence. Remove one of the locks and it is a privilege-escalation
primitive again.

### 5.2 The edit — byte-exact

```
oldStr:
    # Back-office API for the supervisor dashboard (RBAC enforced in the app)
    location /api/ {
      proxy_pass http://business_api/api/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Role $http_x_role;
    }

newStr:
    # Back-office API. Authentication is a bearer token in the Authorization header, which nginx
    # forwards unmodified by default; authorisation is enforced by require_role inside
    # business-api against a principal it resolved itself.
    #
    # This block MUST NOT set a role header. It used to carry
    #     proxy_set_header X-Role $http_x_role;
    # which re-asserted a CLIENT-SUPPLIED header to the API as if the edge had verified it. The
    # edge verifies nothing. P0-1 made business-api ignore the header; P0-2 removed the forward so
    # reviving this deploy target cannot resurrect the escalation path.
    location /api/ {
      proxy_pass http://business_api/api/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
```

### 5.3 Two things deliberately NOT done

1. **No `proxy_set_header Authorization ...` line was added.** nginx forwards the client's
   `Authorization` header to the upstream by default; `Host` and `X-Forwarded-For` are set
   explicitly only because they are *derived* values. Adding a redundant line would imply the
   default is unsafe. It is not.
2. **The `/token/` block is untouched.** It has no role header and needs no change.

### 5.4 Verify

```bash
git grep -n "X-Role\|x_role" -- deploy/ infra/ .github/   # expect: no output
```

**No restart, no rebuild, no container action.** Nothing consumes this file in the running stack.
If you have `nginx` on PATH and want the syntax check for free:

```bash
nginx -t -c "$PWD/deploy/gateway/nginx.conf"   # optional; skip if nginx is absent
```

---

## §6 Change 3 — the second default role, in the admin frontend  ⚠ GATED

**File:** `Frontend/admin_dashboard/src/lib/api/config.ts`
**Do not start this section until §0.4 returned exactly three hits.**

### 6.1 The current state, byte-exact

```ts
export const serverConfig = {
  /** business-api origin. Docker: http://business-api:8108 */
  businessApiUrl: () => optional("BUSINESS_API_URL", "http://localhost:8108").replace(/\/$/, ""),

  /** HMAC key for the session cookie. Generate: openssl rand -hex 32 */
  sessionSecret: () => required("ADMIN_SESSION_SECRET"),

  /** Seeded admin credentials — see §8.1, this is the deliberate stop-gap. */
  adminEmail: () => required("ADMIN_EMAIL"),
  adminPassword: () => required("ADMIN_PASSWORD"),

  /** Backend role granted on login. One of: conseiller | superviseur | administrateur */
  adminRole: () => optional("ADMIN_ROLE", "administrateur"),
  ...
```

Three separate problems, all created by the pre-P0-1 design and all left behind by P0-1:

1. **`adminRole` is a default role that grants `administrateur`.** Its own docstring says
   *"Backend role granted on login."* It is the same defect as `BUSINESS_API_DEFAULT_ROLE`, in
   TypeScript. It is dead — but a reader cannot tell that from this file, and the comment
   actively asserts the opposite.
2. **`adminEmail`/`adminPassword` are `required()`.** The admin app therefore *refuses to start*
   without two variables **nothing reads**. That is why the app `.env` carries the junk values
   `admin@nexus.io` / `change-me`: someone had to put *something* there to make it boot. A
   required-but-unread secret is worse than useless — it trains people to invent values for
   security-shaped variables.
3. **The comment `see §8.1, this is the deliberate stop-gap`** references a cookbook section that
   described the *old* hardcoded-credential login. That design is gone. The comment now points
   at nothing.

### 6.2 The edit — byte-exact

```
oldStr:
  /** Seeded admin credentials — see §8.1, this is the deliberate stop-gap. */
  adminEmail: () => required("ADMIN_EMAIL"),
  adminPassword: () => required("ADMIN_PASSWORD"),

  /** Backend role granted on login. One of: conseiller | superviseur | administrateur */
  adminRole: () => optional("ADMIN_ROLE", "administrateur"),

  /** Session lifetime in seconds. Default 8 h — one shift. */

newStr:
  /*
   * There is deliberately no adminEmail / adminPassword / adminRole here.
   *
   * Before P0-1 this process compared the submitted credentials against ADMIN_EMAIL and
   * ADMIN_PASSWORD and then minted a session with ADMIN_ROLE (defaulting to administrateur).
   * Since P0-1, login POSTs to /api/v1/auth/login and business-api verifies a scrypt hash in
   * auth.portal_accounts; the role in the cookie is the role the BACKEND returned. This process
   * no longer holds, compares, or can leak a password, and it cannot choose a role.
   *
   * ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_ROLE still exist — they are read by
   * business_api.seed_admin to bootstrap that one staff row. They are backend variables. They
   * are not this application's business, and requiring them here only forced operators to
   * invent placeholder values to make the app boot.
   */

  /** Session lifetime in seconds. Default 8 h — one shift. */
```

### 6.3 Why this cannot break the admin login

Stated explicitly because this is the one edit in P0-2 that touches a running application:

| Question | Answer |
| --- | --- |
| Does login read these? | No. `auth.server.ts::login` posts `{email, password}` from the **form** to `/api/v1/auth/login`. It reads `serverConfig.businessApiUrl()` and `requestTimeoutMs()` only. |
| Does the session cookie's role come from `adminRole`? | No. It comes from `result.role` in the backend's login response, and is rejected unless present in `ROLE_RANK`. |
| Does anything else read them? | §0.4 proves it. If that grep found a consumer, you already stopped. |
| Are `required` / `optional` still used after the deletion? | Yes — `required` by `sessionSecret`, `optional` by four accessors. No unused-symbol lint. |
| Does the app still boot with `ADMIN_EMAIL` unset? | That is the point, and §9.2 proves it live. |

### 6.4 What is NOT deleted — read this, it answers the question you asked

You asked: *"after deleting them how admin gonna authenticate to the dashboard?"*

**The admin's static credentials are not being deleted.** They move nowhere and change nowhere:

| Thing | Status after P0-2 |
| --- | --- |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_ROLE` in the **root** `.env` | **STAY.** Live and required. |
| `.env.example` **§22b** documenting them | **STAYS.** Untouched. |
| `business_api.seed_admin` reading them | **STAYS.** Untouched. It is the bootstrap. |
| The seeded row in `auth.portal_accounts` | **STAYS.** Idempotent; re-running leaves it untouched. |
| Admin signs in with those credentials at `/login` | **UNCHANGED.** Still works. |
| Admin can change their own password | **UNCHANGED** — `POST /api/v1/auth/password`, shipped in P0-1. |
| Admin accounts are created by signup | **NO** — and they never will be. Signup is client-only and requires a CIN match against an existing subscriber. |

The *only* thing removed is the **admin frontend's private duplicate** of those three values. The
backend keeps them; the browser-serving app stops pretending it needs them. Your model — static
admin credentials, no admin signup, password changeable — is exactly what remains in place.

### 6.5 Then align the app-level `.env.example`

`Frontend/admin_dashboard/.env.example` exists (1448 B). **I have not read it.** Do this:

```bash
grep -n "ADMIN_EMAIL\|ADMIN_PASSWORD\|ADMIN_ROLE" Frontend/admin_dashboard/.env.example
```

- **Hits →** delete those lines. They now document a requirement that no longer exists.
- **No hits →** nothing to do.

**Keep `ADMIN_SESSION_SECRET`** — `sessionSecret()` still `required()`s it, and without it the app
correctly refuses to start.

Then fix your own machine. `Frontend/admin_dashboard/.env` (gitignored) holds
`admin@nexus.io` / `change-me`:

```bash
# Delete the ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_ROLE lines from
# Frontend/admin_dashboard/.env — they are now unread, and leaving stale credentials
# that do not match the seeded account is a trap for the next reader.
# KEEP ADMIN_SESSION_SECRET.
```

### 6.6 Gates for this file

```bash
cd Frontend/admin_dashboard
./node_modules/.bin/tsc --noEmit          # expect 0
npm run lint                              # expect the SAME non-prettier count as before
npm run build                             # expect success
./node_modules/.bin/prettier --write src/lib/api/config.ts
```

**Do not run `bun run format`.** Prettier the touched file only.

---

## §7 Change 4 — the missing portal environment template

**File:** `Frontend/customer_portal/.env.example` — **NEW**

### 7.1 This is my defect, and this is the fix

P0-1 §11.9 said only that `PORTAL_SESSION_SECRET` must match across nodes. **It never told anyone
to create the portal's `.env` at all**, and the repo ships no template for it — while the admin
app *does* have one (`Frontend/admin_dashboard/.env.example`, 1448 B). The consequence was found
during the browser pass, verbatim: protected routes returned **500** with *"Missing required
environment variable PORTAL_SESSION_SECRET"*. The implementer had to reverse-engineer the file
from the admin's.

One identity layer still means two gitignored secret files. The repo must say so.

### 7.2 The new file

Create `Frontend/customer_portal/.env.example` with exactly this content:

```bash
# Customer portal — server-only configuration.
#
# Copy to .env and fill in:   cp .env.example .env
# .env is gitignored. Never commit it.
#
# Deliberately NOT prefixed with VITE_. The Lovable vite preset injects VITE_* into the CLIENT
# bundle; the backend origin and the session secret must never reach the browser. If you rename
# any of these to VITE_*, you publish the session-signing key to every visitor.

# ---------------------------------------------------------------------------
# business-api origin (server-to-server; the browser never calls it directly)
# ---------------------------------------------------------------------------
# Local dev (portal on the host, business-api published on :8108):
BUSINESS_API_URL=http://localhost:8108
# Inside docker compose, use the service name instead:
# BUSINESS_API_URL=http://business-api:8108

# ---------------------------------------------------------------------------
# Session cookie signing key  —  REQUIRED, the app will not start without it
# ---------------------------------------------------------------------------
# HMAC key for the nexus_portal_session cookie. Generate 32 random bytes as hex:
#     openssl rand -hex 32
# On Windows without openssl, in PowerShell:
#     [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
#
# MUST be different from ADMIN_SESSION_SECRET. They sign two different cookies for two
# different audiences; sharing one key means a leak of either forges both.
#
# MUST be identical on every node serving the portal. The session is an httpOnly cookie
# verified server-side on each request — a node with a different key rejects every cookie
# minted by its peers, which presents as users being randomly signed out behind a load
# balancer.
PORTAL_SESSION_SECRET=

# ---------------------------------------------------------------------------
# Optional — shown with their defaults
# ---------------------------------------------------------------------------
# Session lifetime in seconds. Default 8 h.
# PORTAL_SESSION_TTL=28800

# Upstream request timeout in ms. Default 15 s.
# BUSINESS_API_TIMEOUT_MS=15000
```

### 7.3 Verify

```bash
# The template is tracked; the real file is not.
git check-ignore -v Frontend/customer_portal/.env        # expect: a .gitignore rule matches
git status --short Frontend/customer_portal/             # expect: only .env.example as new
```

If `git check-ignore` reports **no** match, the portal `.gitignore` does not cover `.env` — stop
and report it, because that is a live secret-leak risk and it is a different bug from this one.

### 7.4 Also record it where a deployer will look

Append to `deploy/README.md` (the file already exists to hold exactly this kind of
enforced-by-nothing invariant, and its D13 section is the established format):

```markdown
---

## P0-2 — the two front ends need two DIFFERENT session secrets, each present on every node

### The rule

Both front ends are server-rendered (TanStack Start). Each seals its session into an httpOnly,
HMAC-signed cookie that it verifies server-side on every request:

| App | Cookie | Signing key | Template |
| --- | --- | --- | --- |
| `Frontend/admin_dashboard` | `nexus_admin_session` | `ADMIN_SESSION_SECRET` | `Frontend/admin_dashboard/.env.example` |
| `Frontend/customer_portal` | `nexus_portal_session` | `PORTAL_SESSION_SECRET` | `Frontend/customer_portal/.env.example` |

Two rules, both enforced by nothing:

1. **The two keys MUST differ.** One identity layer does not mean one key. A leaked admin key
   must not forge client sessions, and vice versa.
2. **Each key MUST be identical on every node serving that app.** A node with a different key
   rejects every cookie its peers minted. Symptom: users randomly signed out behind a load
   balancer, with no error anywhere.

### Where it breaks

| Topology | Risk |
| --- | --- |
| Single host, one `.env` per app | Safe. |
| Two replicas with independently generated secrets | **Broken.** Intermittent sign-outs, ~50% per request. |
| Helm / Kubernetes | **Broken by default** — nothing makes two pods share a generated value. Put each key in a Secret and mount that same Secret into every replica. |

### Verifying it after a deploy

```bash
# Same app, every replica: identical. Different apps: MUST differ.
kubectl exec deploy/admin-dashboard  -- printenv ADMIN_SESSION_SECRET  | sha256sum
kubectl exec deploy/customer-portal  -- printenv PORTAL_SESSION_SECRET | sha256sum
```

Compare digests, never the raw values.
```

---

## §8 Tests

### 8.1 The four negative tests already exist — confirm, do not re-add

`apps/business-api/tests/test_auth_http.py` already covers the fail-closed contract. Confirm by
location, then move on:

```bash
grep -n "def test_" apps/business-api/tests/test_auth_http.py
```

You are looking for cases asserting: **anonymous → 401**, **forged `X-Role` → 401**, **wrong
machine key → 401**, and **authenticated-but-outranked → 403 with the byte-identical
`requires role >= <min>` body.** All four were verified live as `verify_p0_1.sh` cases 2, 3, 8
and 6/7.

**If any of the four is absent, stop and report.** Do not write a replacement from memory — I
would be guessing at the fixtures, and a near-miss duplicate is worse than a gap.

### 8.2 NEW — the regression guard

**File:** `apps/business-api/tests/test_no_default_role.py` — **NEW**

This is the durable half of P0-2. Deleting a line stops today's problem; this stops next year's.

```python
"""P0-2 regression guard: no role may be obtained from the environment.

Until P0-1, business_api.security resolved a caller's role as

    role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")

so an anonymous request arrived as a full administrator. P0-1 deleted that expression and P0-2
deleted the variable from every template and deployment artefact. This module fails the build if
anyone reintroduces an environment-sourced role default anywhere in the business-api source tree.

It is a static source assertion on purpose: it needs no database, no container and no network, so
it runs in CI on every push regardless of what infrastructure is available.
"""

from __future__ import annotations

from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "business_api"

# Substrings that would indicate a role being read from the environment.
_FORBIDDEN = (
    "BUSINESS_API_DEFAULT_ROLE",
    "DEFAULT_ROLE",
)


def _python_sources() -> list[Path]:
    return sorted(p for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts)


def test_source_tree_was_actually_found() -> None:
    """Guard the guard.

    A wrong _SRC would make every assertion below vacuously true — the test would pass while
    checking nothing. Pin two facts that can only hold if the real tree was located.
    """
    sources = _python_sources()
    assert sources, f"no python sources found under {_SRC}"
    names = {p.name for p in sources}
    assert "security.py" in names, f"security.py missing from {_SRC}; _SRC is wrong"
    assert "main.py" in names, f"main.py missing from {_SRC}; _SRC is wrong"


def test_no_environment_sourced_role_default() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for needle in _FORBIDDEN:
            if needle in text:
                offenders.append(f"{path.relative_to(_SRC)} contains {needle!r}")

    assert not offenders, (
        "An environment-sourced role default was reintroduced. Roles must come only from a "
        "principal business-api resolved itself (bearer token or INTERNAL_API_KEY). "
        + "; ".join(offenders)
    )


def test_security_module_does_not_read_the_environment_for_a_role() -> None:
    """Narrow, high-signal check on the module that carried the defect."""
    security = (_SRC / "security.py").read_text(encoding="utf-8")
    assert "os.getenv" not in security, (
        "security.py reads the environment. Role resolution must depend only on the resolved "
        "principal, never on configuration."
    )
    assert "getenv" not in security
```

> **Why `test_source_tree_was_actually_found` exists.** A negative assertion that can silently
> pass is worthless — the same failure mode as a probe that returns 401 because it is pointed at
> nothing. P0-1 case 20 solved it with a positive control (a live login returning 200 alongside
> the two 401s). This is the same discipline in pytest form.

**Note on `"DEFAULT_ROLE"`:** it is deliberately broader than the exact variable name, so a
renamed reintroduction (`API_DEFAULT_ROLE`, `FALLBACK_DEFAULT_ROLE`) is still caught. If it ever
fires on a legitimate symbol, **narrow the tuple — do not delete the test.**

### 8.3 Run

```bash
python -m pytest apps/business-api/tests/test_no_default_role.py -q   # expect: all passed
python -m pytest apps/business-api/tests -q                          # expect: all passed
ruff check apps/business-api/tests/test_no_default_role.py           # expect: clean
```

**On counts:** the suite total goes **up** by the three tests above and every test passes. I am
deliberately not printing an expected total — I have miscounted checklist totals four times in
this project, and a wrong number invites you to "fix" a healthy suite. **The assertion is
"increases and is green," never a number.**

---

## §9 Verification

### 9.1 `scripts/verify_p0_2.sh` — NEW

Static sweep plus a live re-proof. Deliberately small: the wire behaviour is already covered by
`verify_p0_1.sh`, which **must keep passing 20/20** and is the real regression net.

```bash
#!/usr/bin/env bash
# P0-2 — fail-closed default role. Static sweep + live re-proof.
# Usage: bash scripts/verify_p0_2.sh
set -uo pipefail

API="${BUSINESS_API_HOST:-http://localhost:8108}"
pass=0; fail=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }

# --- static: nothing may reference an environment-sourced role default -------
echo "static sweep"

if git grep -qn "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply' ':!scripts/verify_p0_2.sh'; then
  bad "BUSINESS_API_DEFAULT_ROLE still present:"
  git grep -n "BUSINESS_API_DEFAULT_ROLE" -- . ':!features_to_apply' ':!scripts/verify_p0_2.sh' | sed 's/^/        /'
else
  ok  "1  BUSINESS_API_DEFAULT_ROLE absent from the repo"
fi

if git grep -qn "X-Role\|x_role" -- deploy/ infra/ .github/; then
  bad "2  a role header is still set in deploy/infra/CI:"
  git grep -n "X-Role\|x_role" -- deploy/ infra/ .github/ | sed 's/^/        /'
else
  ok  "2  no role header set anywhere in deploy/, infra/ or .github/"
fi

if git grep -qn "adminEmail\|adminPassword\|adminRole" -- Frontend/; then
  bad "3  dead admin credential/role config still present:"
  git grep -n "adminEmail\|adminPassword\|adminRole" -- Frontend/ | sed 's/^/        /'
else
  ok  "3  admin frontend holds no credential or role config"
fi

if [ -f Frontend/customer_portal/.env.example ]; then
  ok  "4  Frontend/customer_portal/.env.example exists"
else
  bad "4  Frontend/customer_portal/.env.example is missing"
fi

if grep -q "PORTAL_SESSION_SECRET" Frontend/customer_portal/.env.example 2>/dev/null; then
  ok  "5  the portal template documents PORTAL_SESSION_SECRET"
else
  bad "5  the portal template does not mention PORTAL_SESSION_SECRET"
fi

# --- live: fail-closed is still fail-closed ---------------------------------
echo "live re-proof against ${API}"

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

c=$(code "${API}/health")
[ "$c" = "200" ] && ok "6  /health 200 (the API is actually up)" \
                 || bad "6  /health returned ${c} — the API is down; later cases are meaningless"

c=$(code "${API}/api/v1/customers")
[ "$c" = "401" ] && ok "7  anonymous /customers 401" || bad "7  anonymous /customers returned ${c}, expected 401"

c=$(code -H 'X-Role: administrateur' "${API}/api/v1/customers")
[ "$c" = "401" ] && ok "8  forged X-Role: administrateur 401" || bad "8  forged X-Role returned ${c}, expected 401"

c=$(code -H 'X-Role: administrateur' "${API}/api/v1/jobs/retention")
[ "$c" = "401" ] && ok "9  forged X-Role on an admin-gated route 401" || bad "9  returned ${c}, expected 401"

printf '\n  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
```

```bash
chmod +x scripts/verify_p0_2.sh
bash scripts/verify_p0_2.sh      # expect: 9 passed, 0 failed
```

**Case 6 is the positive control.** Without it, cases 7–9 could "pass" because the API is down and
`curl` is returning `000` — which is not `401`, so it would actually fail; but a future edit that
compares loosely would hide it. The control makes the intent explicit.

### 9.2 The proof that Change 3 is safe — boot without the dead variables

This is the one proof that cannot be static, and it is the whole justification for §6.

```bash
cd Frontend/admin_dashboard

# 1. Confirm the app no longer demands the dead variables.
#    First make sure they are absent from this app's .env (§6.5), then:
grep -c "ADMIN_EMAIL\|ADMIN_PASSWORD\|ADMIN_ROLE" .env    # expect: 0

# 2. Start the dev server. Before P0-2 this would throw
#    "Missing required environment variable ADMIN_EMAIL" and die.
npm run dev
```

**Expected:** the server starts. Note the port it prints — the Lovable preset auto-negotiates, and
it came up on **:8081** last session, not `:5173`.

Then, in a browser — **this is the flow that has never once been exercised end to end**, because
the P0-1 browser pass minted cookies directly instead of submitting the form:

| # | Step | Expected |
| --- | --- | --- |
| 1 | Open `http://localhost:8081/login` | The form renders. |
| 2 | Submit the **seeded backend** credentials (`ADMIN_EMAIL` / `ADMIN_PASSWORD` from the **root** `.env` — `admin@telecom.tn` / `admin-secret-change-now`) | Redirect to `/overview`, real data. |
| 3 | DevTools → Application → Cookies | `nexus_admin_session` present, **HttpOnly** ticked. |
| 4 | Submit a **wrong** password | Inline error in the `role="alert"` paragraph. **No cookie set.** |
| 5 | Submit the **old stale** placeholders (`admin@nexus.io` / `change-me`) | **401 — rejected.** They were never real backend credentials. |

**Step 5 is the important one.** It proves the frontend is no longer an authority on credentials:
the values that used to be "the" admin credentials are now simply wrong, because the backend is
the only judge.

> If step 2 fails with a 401, the seeded account does not match your root `.env`. Re-run
> `python -m business_api.seed_admin` and read its output — it prints whether it created the
> account or left an existing one untouched. **Do not "fix" this by putting credentials back into
> `config.ts`.**

### 9.3 Nothing was broken elsewhere

```bash
# P0-1's full wire proof must still be 20/20 — this is the real regression net.
bash scripts/verify_p0_1.sh

# Voice path untouched (no backend source changed, but prove it, do not assume it).
docker compose -p docker-compose \
  -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml logs --tail=40 agent-worker

# Both front ends still typecheck and build.
cd Frontend/admin_dashboard  && ./node_modules/.bin/tsc --noEmit && npm run build
cd ../customer_portal        && ./node_modules/.bin/tsc --noEmit && npm run build
```

### 9.4 No rebuild is required

**Read this before you reach for `docker compose build`.**

P0-2 changes **no backend source file.** `.env.example` is a template that no process reads;
`nginx.conf` has no container; `config.ts` and the `.env.example` files belong to the front ends,
which run from source in dev.

The **only** reason to rebuild is if you also edited a `.py` file — which this patch does not,
except for the new test, and tests are not baked into the image path that serves traffic. The
business-api Dockerfile bakes source, so *when* you do change Python you must rebuild rather than
restart; that rule is unchanged, it simply does not apply here.

---

## §10 Apply order

| # | Step | Why here |
| --- | --- | --- |
| 1 | §0 gates, all of them | §0.3 defines the patch; §0.4 decides whether §6 is legal |
| 2 | §8.2 add `test_no_default_role.py`, run it | It should pass **before** the deletions — the source tree is already clean. If it fails now, §0.3 lied and you must stop |
| 3 | §4 `.env.example` | Documentation only |
| 4 | §5 `nginx.conf` | Nothing consumes it |
| 5 | §7 portal `.env.example` + `deploy/README.md` | Additive |
| 6 | §6 `config.ts` + the two app `.env` files | Last, because it is the only edit that touches a running app |
| 7 | §6.6 admin gates → §9.2 live boot + browser login | Immediately after §6, while the change is fresh |
| 8 | §9.1 `verify_p0_2.sh`, §9.3 regression sweep | Final |

**Step 2 before the deletions is intentional.** The guard is written against a tree that is
*already* clean, so it must pass immediately. A guard that only passes after your edits cannot
distinguish "the property holds" from "my edit happened to satisfy my own test."

---

## §11 Rollback

Every change is a deletion of dead weight or a new file. Rollback is per-file and total:

```bash
git checkout -- .env.example
git checkout -- deploy/gateway/nginx.conf
git checkout -- deploy/README.md
git checkout -- Frontend/admin_dashboard/src/lib/api/config.ts
rm -f Frontend/customer_portal/.env.example
rm -f apps/business-api/tests/test_no_default_role.py
rm -f scripts/verify_p0_2.sh
```

Then restore the three lines in `Frontend/admin_dashboard/.env` if you removed them.

**No migration, no data change, no container action, no dependency change.** There is nothing to
un-migrate and nothing to re-seed. This is the cheapest rollback in the project so far.

---

## §12 Impact analysis

| Surface | Impact |
| --- | --- |
| Backend runtime behaviour | **None.** No `.py` under `src/` is modified. |
| Voice agent / LiveKit flow | **None.** The worker's machine identity (`INTERNAL_API_KEY` → `conseiller`) is untouched. |
| Admin login | Unchanged in behaviour; the app now boots without two variables it never read. |
| Client portal login/signup | **None.** A template is added; no code changes. |
| Database | **None.** No migration, no seed change. |
| Existing sessions | **None.** Cookie format, signing key and TTL all unchanged — nobody is signed out. |
| CORS | **None.** |
| Dependencies | **None.** No pip, no npm. |
| Design system | **None.** No component, colour, token or copy touched. |
| CI | One new test file, offline and deterministic — no services required. |

**Who could notice this patch in production?** Only an operator who had `ADMIN_EMAIL` set for the
admin *app* and expected it to matter. It did not matter before this patch either.

---

## §13 Confidence

| Item | Confidence | Basis |
| --- | --- | --- |
| §4 `.env.example` deletion is behaviourally inert | **Very high** | P0-1 already proved nothing reads it; verify cases 2/3 are 401 |
| §5 `nginx.conf` deletion is inert | **Very high** | No nginx container in either compose file; read both |
| §6 `config.ts` deletion is safe | **High, gated** | I read the post-P0-1 `auth.server.ts` body and it reads neither. Gated on §0.4 because I did not read all 21 other `*.server.ts` files for this symbol |
| §7 portal template content is correct | **High** | Mirrors the portal's own `config.ts` key names, which I read |
| §8.2 guard is durable and non-flaky | **High** | Pure filesystem read, no I/O beyond the repo |
| The sweep is complete | **Medium — and this is the weak point** | I read 9 files and 7 listings. `infra/helm/telecom-platform/**`, `deploy/helm/.../templates/**` and `infra/ci-cd/**` are **unread**. §0.3 is what actually closes this, not my table |

**The honest weak point is the sweep.** Everything else here is a deletion whose inertness is
proven. If §0.3 surfaces a hit I did not predict, my §3 table was incomplete — report it rather
than absorbing it silently, because a *live* `BUSINESS_API_DEFAULT_ROLE` in a helm chart would
mean some deploy target was configured to grant a default role, which is a genuine finding and
not a documentation cleanup.

---

## §14 File manifest — authoritative

**Modified (4):**

| File | Change |
| --- | --- |
| `.env.example` | delete `BUSINESS_API_DEFAULT_ROLE` + its P0-1 annotation; add the §4.3 prohibition block |
| `deploy/gateway/nginx.conf` | delete `proxy_set_header X-Role $http_x_role;`; rewrite the block comment |
| `deploy/README.md` | append the §7.4 session-secret invariant |
| `Frontend/admin_dashboard/src/lib/api/config.ts` | delete `adminEmail`, `adminPassword`, `adminRole` |

**Created (3):**

| File |
| --- |
| `Frontend/customer_portal/.env.example` |
| `apps/business-api/tests/test_no_default_role.py` |
| `scripts/verify_p0_2.sh` |

**Conditionally modified (2), gitignored or contents-unread:**

| File | Condition |
| --- | --- |
| `Frontend/admin_dashboard/.env.example` | only if §6.5's grep finds `ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_ROLE` |
| `Frontend/admin_dashboard/.env` | local only — drop the three stale lines, keep `ADMIN_SESSION_SECRET` |

**Explicitly NOT touched:** any `.py` under `apps/business-api/src/`, `packages/**`,
`apps/agent-worker/**`, all `alembic/versions/**`, `security.py`, `require_role`, the root `.env`
`ADMIN_*` variables, `.env.example` §22b, `seed_admin.py`, `status.ts`, any component or design
token, `apps/supervisor-dashboard/**` (see §16.3).

---

## §15 STEP 8 — completion report to return to me

Fill this in and send it back. **Report what you observed, not what this document predicted** —
every divergence so far has been the cookbook's error, not the repo's.

```markdown
# P0-2 — completion report

Branch / HEAD:

## Gate results (§0)
- 0.1 branch / alembic head:
- 0.2 verify_p0_1.sh before starting:            /20
- 0.3 sweep A (BUSINESS_API_DEFAULT_ROLE) — locations found:
- 0.3 sweep B (X-Role in deploy/infra/CI) — locations found:
- 0.3 sweep C (other DEFAULT_ROLE spellings) — locations found:
- 0.3 ANY UNEXPECTED LOCATION? (yes/no + what):
- 0.4 adminEmail/adminPassword/adminRole hits (expect exactly 3 definitions):
- 0.4 any CONSUMER found? (yes/no — if yes, §6 was NOT applied):
- 0.5 `ruff check .` repo-wide result (recorded, NOT fixed):

## Changes applied
- §4 .env.example:                     applied / skipped — note:
- §5 nginx.conf:                       applied / skipped
- §6 config.ts:                        applied / SKIPPED because §0.4 found a consumer
- §6.5 admin .env.example:             edited / no hits / n-a
- §6.5 admin .env local:               cleaned / n-a
- §7 portal .env.example:              created
- §7.4 deploy/README.md:               appended
- §8.2 test_no_default_role.py:        created
- §9.1 verify_p0_2.sh:                 created

## Verification
- test_no_default_role.py BEFORE the deletions (must pass):
- pytest full suite: increased and green? (yes/no)
- verify_p0_2.sh:                                /9
- verify_p0_1.sh AFTER the patch (must still be 20/20):        /20
- admin tsc / lint / build:
- portal tsc / build:
- §9.2 admin dev server booted with ADMIN_EMAIL absent? (yes/no)
- §9.2 browser step 2 — form login with SEEDED creds → /overview:
- §9.2 browser step 3 — nexus_admin_session cookie, HttpOnly:
- §9.2 browser step 4 — wrong password, no cookie:
- §9.2 browser step 5 — stale admin@nexus.io / change-me now REJECTED:
- agent-worker logs clean:

## Deviations
(one line each: what the cookbook said, what the repo actually had, what you did)

## Anything you found that I did not predict
```

---

## §16 Handoff

### 16.1 P0-3 — persist agent turns  ⚠ read this before starting it

P0-3 is next in the §2 order. Two things about it are already known and both are traps:

1. **Zero frontend work.** `transcript.tsx` already renders both `caller` and `agent` turns. The
   writer chain is `base_agent.py:181-184` → `writer.py:124,132`, and the CHECK constraint at
   `conversation.py:67` already permits `speaker IN ('caller','agent')`. Use the **existing**
   writer — the roadmap forbids a second mechanism.

2. **P0-3 and P1-1 must ship together, or a shipped label becomes a lie.** Every one of the ~490
   existing turns has `speaker="caller"`, and `repositories.py::agent_activity()` has **no
   `speaker` predicate**. FEATURE_20 renamed that metric's label to **"Caller turns"** on the
   strength of that. The moment agent turns start persisting, `agent_activity()` counts both and
   the label is wrong.

   > `agent_activity()` needs `.where(Turn.speaker == "caller")` **in the same change** that makes
   > agent turns persist. Not in a follow-up. This was tracked as candidate FEATURE_22; it folds
   > into P1-1.

### 16.2 CI defects found while sweeping — for P1-3, do not fix them here

Reading `.github/workflows/ci.yml` (blob `a62ea96c`) for the sweep turned up three real defects.
All belong to **P1-3**, which is explicitly about CI:

| # | Defect | Consequence |
| --- | --- | --- |
| a | The `test` job loops over 6 packages, 6 services and `apps/business-api` — but **never `apps/agent-worker`** | The voice agent's tests never run in CI. This *is* P1-3. |
| b | `lint` runs `ruff check .` repo-wide while `main.py` still reports errors | Unless `pyproject.toml` carries a per-file ignore I have not read, **that job is failing**. See §0.5. |
| c | The `docker-build` matrix uses `file: services/${{ matrix.service }}/Dockerfile` but includes `token-service`, `business-api` and `agent-worker`, which live under `apps/` | Those three legs must fail. Masked because the job is `if: github.ref == 'refs/heads/main'`, and `docker-build-apps` already does it correctly with the `apps/` path. |

### 16.3 Still open, unchanged by P0-2

- **`apps/supervisor-dashboard/src/api.ts` still sends `X-Role` to `:8108`** and those calls now
  401. It is the last front-app source carrying the header. It is **not** a compose service, so
  the breakage is real but dormant. `Makefile` targets `frontends` / `frontends-clean` still
  install it and `apps/client-widget`. Decision needed: rewire through a server or delete. *(I
  previously claimed these two apps no longer exist. That was wrong — both are present at
  `version_83`. Correction stands on the record.)*
- Rate-limit bucket pruning; expired `portal_sessions` in `jobs/retention.py`.
- The portal's remaining `/me/*` surfaces (billing, services, requests, activity) still render
  fixtures, so a signed-in client still sees **Amara Osei**.
- `.env.example` `BUSINESS_API_URL=http://localhost:8107` is wrong twice (8107 is token-service;
  business-api is 8108) — **P1-2 item K**, not this patch.
- `CORS_ORIGINS` lists `:5173,:5174` but the dev servers negotiate **:8081** and **:8080**.
  Harmless today because both front ends proxy server-side.
- `Makefile seed` runs neither `seed_auth_credentials` nor `seed_admin`.
- 60 pre-existing prettier errors in portal route files untouched by P0-1.
- Open architectural question: **should authentication events enter `audit.audit_ledger`?** The
  ledger currently records *what*, never *who*. Answering it is a design decision, not a cleanup.

---

**End of P0-2.**
