# Feature 0 — Integration Substrate (transport, auth, data-fetching, UI states)

> **Cookbook 0 of the admin-dashboard wiring series.**
> Nothing else in the series is implementable until this exists. Every later cookbook
> (Advisors, Callbacks, Calls, Tickets, RAG, Guardrails, KPIs) assumes the primitives
> defined here and does nothing but consume them.

| Field | Value |
|---|---|
| Repository | `chouaib-saad/livekit_agent` |
| Source of truth | branch **`version_79`**, SHA `eda5f58ff3f468755db455e445eb6117b6909b5c` |
| Scope | Admin dashboard only (`Frontend/admin_dashboard`). Customer portal untouched. |
| Transport decision | **Proxy via the TanStack Start server layer** (confirmed by you) |
| Auth decision | **In scope for Feature 0** (confirmed by you) |
| Backend files modified | **ZERO** |
| Backend files created | **ZERO** |
| New npm dependencies | **ZERO** |
| New design tokens | **ZERO** |
| Frontend files created | 9 |
| Frontend files modified | 5 |

---

## Table of contents

1. [Feature name & scope](#1-feature-name--scope)
2. [Backend reference](#2-backend-reference)
3. [Endpoints](#3-endpoints)
4. [Decisions & justifications](#4-decisions--justifications)
5. [Frontend implementation plan](#5-frontend-implementation-plan)
6. [Full code](#6-full-code)
7. [Validation checklist](#7-validation-checklist)
8. [Ambiguities needing your confirmation](#8-ambiguities-needing-your-confirmation)

---

## 1. Feature name & scope

**Feature 0 — Integration Substrate.**

This is not a user-facing feature. It is the shared plumbing that makes every user-facing
cookbook a thin, boring mapping exercise.

### In scope

| # | Deliverable | Why it belongs in Feature 0 |
|---|---|---|
| 0.1 | Server-side HTTP client to `business-api` | Every feature calls it |
| 0.2 | Typed error model (`ApiError`) | Every feature renders errors |
| 0.3 | Environment/config resolution | Every feature needs the base URL |
| 0.4 | Admin session (login, logout, signed cookie) | Gates all data |
| 0.5 | Auth middleware attached to every server function | The real security boundary |
| 0.6 | `X-Role` injection, server-side only | Backend RBAC contract |
| 0.7 | Route-level auth gate (UX layer) | Keeps users off dead screens |
| 0.8 | TanStack Query defaults + query-key factory | Prevents per-feature drift |
| 0.9 | Loading / error UI states | Template has neither |
| 0.10 | Real identity in the topbar (replaces hardcoded `ACCOUNT`) | Proves the session end-to-end |

### Explicitly out of scope

- Any data table, chart, or feature screen. Those are cookbooks 1–10.
- The customer portal (`Frontend/customer_portal`).
- OIDC / SSO — see [§8](#8-ambiguities-needing-your-confirmation).
- Any change to backend business logic.

---

## 2. Backend reference

### 2.1 Service under integration

| Item | Value |
|---|---|
| App | `apps/business-api` |
| Package root | `apps/business-api/src/business_api/` |
| Entrypoint | `business_api/main.py` (blob `ff52daff5df92f0d40a9f052564c18235625e55e`) |
| Framework | FastAPI, `app = FastAPI(title="business-api")` |
| Port | `8108` — `uvicorn.run(app, host="0.0.0.0", port=8108)` in `run()` |
| Console script | `business-api` (per `[project.scripts]`) |
| Health probe | `GET /health` → `{"status": "ok"}` |
| API prefix | `/api/v1` |

### 2.2 Supporting modules (read, not modified)

| Path | Role |
|---|---|
| `business_api/security.py` | RBAC dependency factory `require_role()` |
| `business_api/repositories.py` | `SupervisionRepository` — customer 360, sessions, KPIs, verdicts, actions |
| `business_api/advisors.py` | Advisor registry CRUD + claim/release |
| `business_api/availability.py` | Shift grids, time-off, coverage report |
| `business_api/callbacks.py` | Callback queue, slot negotiation |
| `business_api/policy_view.py` | Overlays live `POLICY_*` env onto the rule registry |
| `business_api/kpis.py` | KPI dataclass |
| `business_api/jobs/integrity.py` | Referential integrity + audit-chain verification |
| `business_api/jobs/retention.py` | Audited retention/purge job |
| `packages/audit-trail` → `PgAuditLedger` | Hash-chain ledger (`verify()`, `count()`) |
| `packages/persistence` → `get_session` | SQLAlchemy session dependency |

### 2.3 The RBAC contract — read this carefully

`apps/business-api/src/business_api/security.py`, in full:

```python
"""API-layer RBAC (spec section 19): conseiller < superviseur < administrateur.

The role matrix is enforced here. Real identity is OIDC at integration time; in this build the
role is taken from the `X-Role` header (or BUSINESS_API_DEFAULT_ROLE for local use).
"""
_ROLE_RANK = {"conseiller": 1, "superviseur": 2, "administrateur": 3}


def require_role(minimum: str):
    minimum_rank = _ROLE_RANK[minimum]

    def _dependency(x_role: str | None = Header(default=None)) -> str:
        role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
        if role_rank(role) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
        return role

    return _dependency
```

**Four facts that drive this entire cookbook:**

1. **There is no authentication.** There is only *authorization*, and it trusts a header.
2. **The caller declares its own role.** `X-Role: administrateur` grants full access to anyone
   who can reach the port.
3. **The fallback is the most privileged role.** If `X-Role` is absent and
   `BUSINESS_API_DEFAULT_ROLE` is unset, the caller is treated as `administrateur`.
4. **The docstring states the intent**: *"Real identity is OIDC at integration time."* Identity
   was deliberately deferred, not forgotten.

> **Consequence — this is why your proxy choice was the correct one.**
> Under the *direct* transport, the browser would have to send `X-Role` itself. Any user could
> open devtools and replay a request with `X-Role: administrateur`, and any unauthenticated
> person who could reach `:8108` would already be an admin. Under the *proxy* transport the
> browser never sends `X-Role`, never learns the backend URL, and cannot reach `:8108` at all.

> **Constraint-3 boundary.** Implementing OIDC would be *building missing business logic*, which
> your constraint 3 forbids. So Feature 0 adds authentication **at the frontend server edge**,
> where it is access plumbing, and leaves `security.py` byte-for-byte untouched. See
> [§4.3](#43-decision-3--where-authentication-lives) and [§8.1](#81-blocking--admin-identity-source).

### 2.4 CORS — already present, and now irrelevant

`main.py` lines 27–33:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(","),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Role"],
)
```

Your constraint 3(a) pre-authorised adding CORS. **No CORS work is needed:**

- It already exists, already allows every verb the dashboard uses, and already allows `X-Role`.
- Under the proxy transport the request is server→server, so CORS never engages. Browsers only
  enforce CORS on browser-originated cross-origin requests.

**No backend code change. Two production *configuration* notes only** (not code, not in scope,
flagged for your ops checklist):

- `BUSINESS_API_DEFAULT_ROLE` should be set to `conseiller` in production so that a missing
  header fails closed at the lowest privilege instead of open at the highest.
- `CORS_ORIGINS` should not include a public origin, since no browser needs direct access.

---

## 3. Endpoints

### 3.1 Existing endpoints — the complete inventory

Every endpoint in `main.py`, with the minimum role enforced. **This table is the contract for
every later cookbook**; each one will cite rows from it rather than re-deriving them.

| # | Method | Path | Min role | Purpose | Cookbook |
|---|---|---|---|---|---|
| 1 | GET | `/health` | none | Liveness | 0 |
| 2 | GET | `/api/v1/customers/{customer_id}/360` | conseiller | Profile + subs + invoices + tickets | Customers |
| 3 | GET | `/api/v1/sessions/{session_id}` | conseiller | Masked transcript + sentiment + disposition | Calls |
| 4 | GET | `/api/v1/escalations` | superviseur | Escalation queue (`?status=open`) | Calls |
| 5 | GET | `/api/v1/policy/verdicts` | superviseur | Verdicts for a session (`?session_id=`) | Guardrails |
| 6 | GET | `/api/v1/actions` | superviseur | Action ledger (`?status=failed`) | Decisions |
| 7 | GET | `/api/v1/kpis` | superviseur | Containment / escalation KPIs | KPIs |
| 8 | GET | `/api/v1/system/overview` | superviseur | DB counts + service status matrix | Overview |
| 9 | GET | `/api/v1/telemetry/timeline` | superviseur | Time-series + verdict distributions | Analytics |
| 10 | GET | `/api/v1/audit/verify` | administrateur | Hash-chain integrity | Decisions |
| 11 | GET | `/api/v1/reference/business-rules` | administrateur | Rule registry + LIVE thresholds | Guardrails |
| 12 | GET | `/api/v1/jobs/integrity` | administrateur | Referential integrity report | Decisions |
| 13 | POST | `/api/v1/jobs/retention` | administrateur | Retention job (`?dry_run=true`) | Settings |
| 14 | GET | `/api/v1/advisors/coverage` | superviseur | Hour-by-hour coverage (`?days=7`) | Availability |
| 15 | GET | `/api/v1/advisors/{advisor_id}/schedule` | superviseur | Weekly grid + absences | Availability |
| 16 | PUT | `/api/v1/advisors/{advisor_id}/schedule` | administrateur | Replace weekly grid | Availability |
| 17 | GET | `/api/v1/advisors/{advisor_id}/time-off` | superviseur | Absences | Availability |
| 18 | POST | `/api/v1/advisors/{advisor_id}/time-off` | administrateur | Create absence (201) | Availability |
| 19 | DELETE | `/api/v1/advisors/time-off/{time_off_id}` | administrateur | Cancel absence | Availability |
| 20 | GET | `/api/v1/advisors` | superviseur | List advisors (`?include_inactive=`) | Advisors |
| 21 | POST | `/api/v1/advisors` | administrateur | Create advisor (201) | Advisors |
| 22 | PATCH | `/api/v1/advisors/{advisor_id}` | administrateur | Update advisor | Advisors |
| 23 | DELETE | `/api/v1/advisors/{advisor_id}` | administrateur | Delete advisor | Advisors |
| 24 | POST | `/api/v1/advisors/claim` | conseiller | Reserve advisor (agent-facing) | — |
| 25 | POST | `/api/v1/advisors/{advisor_id}/release` | conseiller | Release advisor (agent-facing) | — |
| 26 | GET | `/api/v1/advisors/on-call` | conseiller | On-call advisors | Advisors |
| 27 | GET | `/api/v1/callbacks/slots` | conseiller | Bookable slots | Callbacks |
| 28 | GET | `/api/v1/callbacks/check` | conseiller | Is this time bookable + alternatives | Callbacks |
| 29 | POST | `/api/v1/callbacks/reserve` | conseiller | Book a slot (201, 409 on race) | Callbacks |
| 30 | GET | `/api/v1/callbacks` | conseiller | Queue (`?status=&overdue_only=&limit=`) | Callbacks |
| 31 | GET | `/api/v1/callbacks/stats` | superviseur | Queue health | Callbacks |
| 32 | POST | `/api/v1/callbacks/claim` | conseiller | Take next due callback | Callbacks |
| 33 | POST | `/api/v1/callbacks/{callback_id}/complete` | conseiller | Close with outcome | Callbacks |
| 34 | POST | `/api/v1/callbacks/{callback_id}/cancel` | superviseur | Cancel | Callbacks |

**Coverage read:** 34 endpoints already exist. Of the twelve nav destinations, **Advisors,
Callbacks, Analytics, Overview, Policies, Rules and Customers are already fully or largely
served.** The gaps that will need additive endpoints in later cookbooks are **Tickets**,
**Knowledge/RAG**, and the **call-log list view** (endpoint 3 fetches *one* session by id; there
is no list-sessions endpoint). Those gaps are named here so they are not a surprise later; they
are **not** addressed in Feature 0.

### 3.2 New endpoints to create in Feature 0

**None.**

This is a deliberate and, I think, important result: the substrate is a pure frontend concern,
and the backend already exposes `/health` for the connectivity check. Feature 0 touches zero
Python files.

### 3.3 CORS / middleware changes in Feature 0

**None.** See [§2.4](#24-cors--already-present-and-now-irrelevant).

---

## 4. Decisions & justifications

### 4.1 Decision 1 — proxy, and where the boundary sits

**Chosen:** browser → TanStack Start server (same origin) → `business-api:8108`.

| | Direct | **Proxy (chosen)** |
|---|---|---|
| `X-Role` forgeable by user | **Yes** | No — injected server-side |
| Backend port publicly reachable | Required | Never exposed |
| CORS config needed | Yes | No |
| Secrets in browser bundle | Base URL, role | None |
| Extra network hop | No | Yes (intra-cluster, negligible) |

Given [§2.3](#23-the-rbac-contract--read-this-carefully), Direct is not merely less tidy — it is
insecure by construction, because the backend's only access control is a header the browser
would control.

### 4.2 Decision 2 — server functions, not server routes

TanStack Start offers both. I use `createServerFn` because:

- It is **typed end-to-end** — the handler's return type flows to the caller with no shared
  interface file and no codegen.
- `src/start.ts` **already installs `createCsrfMiddleware`** filtered to
  `ctx.handlerType === "serverFn"`. Choosing server functions means every mutation inherits CSRF
  protection that is already configured and already tested. Server routes would sit outside that
  filter and would need their own protection.
- No outside consumer needs these endpoints; they exist solely for this dashboard.

### 4.3 Decision 3 — where authentication lives

The TanStack Start authentication guide is unambiguous, and it contradicts the pattern most
tutorials show:

> *"A route guard is not a data authorization boundary. Server functions and server routes are
> API endpoints; they are reachable independently of the route that calls them. Auth must be
> enforced in the handler or middleware for the endpoint that touches private data. `beforeLoad`
> is for route UX."*
> — [Authentication Server Primitives](https://tanstack.com/start/v0/docs/framework/react/guide/authentication-server-primitives)

So Feature 0 enforces auth in **two places with two different jobs**, and it is important not to
confuse them:

| Layer | File | Job | Is it the security boundary? |
|---|---|---|---|
| `authedMiddleware` | `src/lib/api/middleware.ts` | Rejects unauthenticated calls, resolves role, injects `X-Role` | **Yes** |
| `beforeLoad` in `__root.tsx` | `src/routes/__root.tsx` | Redirects to `/login` so users never see a broken screen | No — UX only |

**Every server function that touches backend data must attach `authedMiddleware`.** A route guard
alone would leave the underlying RPC endpoint publicly callable.

### 4.4 Decision 4 — root `beforeLoad` gate instead of an `_authed` layout route

The idiomatic TanStack pattern is a pathless layout route (`_authed.tsx`) with children moved to
`src/routes/_authed/*.tsx`. **I rejected it.**

- It requires renaming all 13 existing route files, which regenerates `routeTree.gen.ts` wholesale
  and produces a very large diff.
- `Frontend/admin_dashboard/AGENTS.md` warns that this project is **connected to Lovable** and that
  commits sync back into the editor. A 13-file structural rename is exactly the kind of change most
  likely to cause a messy sync.
- The gate is UX-only anyway ([§4.3](#43-decision-3--where-authentication-lives)), so the extra
  structure buys no security.

**Chosen instead:** a single `beforeLoad` on the existing root route with a `/login` exemption.
Zero file renames, no change to `routeTree.gen.ts`.

### 4.5 Decision 5 — signed cookie session, zero new dependencies

Session state is an HMAC-SHA-256-signed, `httpOnly`, `SameSite=Lax` cookie.

- Signing uses **Web Crypto** (`globalThis.crypto.subtle`), available in Node 18+ *and* in
  Cloudflare Workers — and `vite.config.ts` documents that the Lovable preset builds with
  **nitro targeting cloudflare by default**, so a Node-only library such as `jsonwebtoken` could
  break the production build.
- No new npm package is added, so `bun.lock` stays clean and nothing new syncs into Lovable.
- The cookie holds only `{ sub, role, exp }`. It is a bearer of *role*, matching exactly what the
  backend consumes — no richer identity is invented that the backend could not honour.

### 4.6 Decision 6 — the three UI states

Audit of `src/components/nexus/primitives.tsx` (15.7 KB, 18 exports):

`Card`, `CardHeader`, `Avatar`, `Token`, `StatusChip`, `PriorityMeter`, `PresenceDot`, `Button`,
`IconButton`, `Delta`, `EmptyState`, `TableShell`, `Th`, `Td`, `SearchInput`, `Tabs`, `Segmented`,
`Checkbox`, `Sparkline`.

- **`EmptyState` exists** → reuse verbatim, never re-implement.
- **No loading state exists.**
- **No error state exists.**
- **No text input exists** other than the one inside `SearchInput`.

A mock-data template needs none of these; a real-data dashboard needs all three. Per your
constraint 1, I add them **by composition from existing tokens only**:

| New component | Built from | New tokens? |
|---|---|---|
| `TableSkeleton` | `Td`/`tr` + `bg-surface-4` + Tailwind's built-in `animate-pulse` | No |
| `ErrorState` | Structural clone of `EmptyState` + existing `Button` | No |
| `TextField` | The **exact** `className` string lifted from `SearchInput`'s `<input>` | No |

`TextField` deserves a word: rather than author a new field style, I copied the input class string
out of `SearchInput` character-for-character. The login field is therefore guaranteed pixel-identical
to the search field already shipping in the topbar.

### 4.7 Decision 7 — replace the hardcoded `ACCOUNT`

`src/lib/nexus/nav.ts` ends with:

```ts
export const ACCOUNT = {
  name: "Chouaib Saad",
  role: "Administrator",
  email: "chouaib.saad@nexus.io",
  initials: "CS",
};
```

This is mock data consumed by `app-topbar.tsx`. Feature 0 replaces it with the live session. I keep
the **export name and object shape** so the topbar diff stays tiny, and derive `initials` with the
existing `initials()` helper from `src/lib/nexus/format.ts` rather than writing new logic.

### 4.8 Decision 8 — role vocabulary stays French

The backend ranks `conseiller < superviseur < administrateur`. The UI template says
`"Administrator"`. I **keep the backend identifiers as the wire values** and map to display labels
only at render time. Rationale: per your constraint, the backend is the source of truth; inventing
an English enum would create a translation layer that could silently desynchronise from
`_ROLE_RANK`.

---

## 5. Frontend implementation plan

### 5.1 Files created (9)

| # | Path | Purpose |
|---|---|---|
| C1 | `src/lib/api/errors.ts` | `ApiError` + status helpers |
| C2 | `src/lib/api/config.ts` | Server-only env resolution |
| C3 | `src/lib/api/session.ts` | HMAC sign/verify, cookie read/write |
| C4 | `src/lib/api/business-api.ts` | Server-only fetch client, injects `X-Role` |
| C5 | `src/lib/api/middleware.ts` | `authedMiddleware` — the security boundary |
| C6 | `src/lib/api/auth.server.ts` | `login` / `logout` / `getSession` server fns |
| C7 | `src/lib/nexus/query-keys.ts` | Central query-key factory |
| C8 | `src/components/nexus/states.tsx` | `TableSkeleton`, `ErrorState`, `CardSkeleton` |
| C9 | `src/routes/login.tsx` | Login screen |

Plus `.env.example` at `Frontend/admin_dashboard/.env.example`.

### 5.2 Files modified (5)

| # | Path | Change | Size |
|---|---|---|---|
| M1 | `src/router.tsx` | Query defaults + `session` in router context | ~10 lines |
| M2 | `src/routes/__root.tsx` | `beforeLoad` gate; `/login` renders bare | ~25 lines |
| M3 | `src/lib/nexus/nav.ts` | `ACCOUNT` → `AccountInfo` type + fallback | ~12 lines |
| M4 | `src/components/nexus/app-topbar.tsx` | Real session + sign-out | ~30 lines |
| M5 | `src/components/nexus/primitives.tsx` | Append `TextField` | ~30 lines |

### 5.3 Data flow

```
browser (no secrets, no X-Role, no backend URL)
   │  useQuery(...)  — same-origin RPC, CSRF-protected
   ▼
createServerFn().middleware([authedMiddleware]).handler(...)
   │  1. read signed cookie   → 401 if absent/expired/tampered
   │  2. resolve role          → 403 if rank too low
   │  3. inject X-Role         ← the ONLY place this header is ever set
   ▼
businessApi() → fetch(`${BUSINESS_API_URL}/api/v1/...`)
   ▼
FastAPI  require_role(...)  → SupervisionRepository → PostgreSQL
```

### 5.4 State contract every later cookbook must follow

| State | Condition | Render |
|---|---|---|
| Loading | `isPending` | `<TableSkeleton>` / `<CardSkeleton>` |
| Error | `isError` | `<ErrorState>` with `refetch` |
| Empty | success, `length === 0` | `<EmptyState>` (existing) |
| Success | otherwise | The real table/chart |
| Forbidden | `ApiError.status === 403` | `<ErrorState>` with the insufficient-role copy |

---

## 6. Full code

### C1 — `src/lib/api/errors.ts` (new)

```ts
/** Typed transport errors. Thrown server-side, serialised to the client by TanStack Start. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly path: string;

  constructor(status: number, detail: string, path: string) {
    super(`business-api ${status} on ${path}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.path = path;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError || (error as ApiError)?.name === "ApiError";
}

/** 401 — the session is gone. The UI must send the user back to /login. */
export function isUnauthenticated(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

/** 403 — authenticated but out-ranked. Matches require_role() in security.py. */
export function isForbidden(error: unknown): boolean {
  return isApiError(error) && error.status === 403;
}

/** Human-readable copy for <ErrorState>. Never leaks a stack trace. */
export function errorMessage(error: unknown): string {
  if (isForbidden(error)) return "Your role does not grant access to this data.";
  if (isUnauthenticated(error)) return "Your session has expired. Sign in again.";
  if (isApiError(error)) return error.detail || "The service returned an unexpected response.";
  return "Could not reach the service. Check that business-api is running.";
}
```

### C2 — `src/lib/api/config.ts` (new)

```ts
/**
 * Server-only configuration. Never imported from a component.
 *
 * Deliberately NOT prefixed with VITE_: the Lovable vite preset injects VITE_* into the client
 * bundle, and the backend URL and session secret must never reach the browser.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Copy .env.example to .env and fill it in.`,
    );
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] || fallback;
}

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

  /** Session lifetime in seconds. Default 8 h — one shift. */
  sessionTtlSeconds: () => Number(optional("ADMIN_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  isProduction: () => process.env.NODE_ENV === "production",
} as const;
```

### C3 — `src/lib/api/session.ts` (new)

```ts
import { getCookie, setCookie } from "@tanstack/react-start/server";
import { serverConfig } from "./config";

export const SESSION_COOKIE = "nexus_admin_session";

/** Backend role vocabulary — mirrors _ROLE_RANK in business_api/security.py. */
export type BackendRole = "conseiller" | "superviseur" | "administrateur";

export const ROLE_RANK: Record<BackendRole, number> = {
  conseiller: 1,
  superviseur: 2,
  administrateur: 3,
};

/** Display labels. The wire value stays French; only the label is translated. */
export const ROLE_LABEL: Record<BackendRole, string> = {
  conseiller: "Advisor",
  superviseur: "Supervisor",
  administrateur: "Administrator",
};

export type AdminSession = {
  /** Subject — the admin's email. */
  sub: string;
  role: BackendRole;
  /** Expiry, epoch seconds. */
  exp: number;
};

/* ---------- base64url (no padding) ---------- */

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/* ---------- HMAC-SHA-256 via Web Crypto (Node 18+ and Cloudflare Workers) ---------- */

async function hmacKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(serverConfig.sessionSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

/** Constant-time comparison — avoids leaking signature bytes through timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function signSession(session: AdminSession): Promise<string> {
  const payload = toBase64Url(new TextEncoder().encode(JSON.stringify(session)));
  const signature = await crypto.subtle.sign(
    "HMAC",
    await hmacKey(),
    new TextEncoder().encode(payload),
  );
  return `${payload}.${toBase64Url(new Uint8Array(signature))}`;
}

export async function verifySession(token: string | undefined): Promise<AdminSession | null> {
  if (!token) return null;

  const separator = token.lastIndexOf(".");
  if (separator <= 0) return null;

  const payload = token.slice(0, separator);
  const signature = token.slice(separator + 1);

  const expected = toBase64Url(
    new Uint8Array(
      await crypto.subtle.sign("HMAC", await hmacKey(), new TextEncoder().encode(payload)),
    ),
  );
  if (!timingSafeEqual(signature, expected)) return null;

  try {
    const session = JSON.parse(new TextDecoder().decode(fromBase64Url(payload))) as AdminSession;
    if (typeof session.exp !== "number" || session.exp * 1000 < Date.now()) return null;
    if (!(session.role in ROLE_RANK)) return null;
    return session;
  } catch {
    return null;
  }
}

/* ---------- cookie I/O ---------- */

export async function writeSessionCookie(session: AdminSession): Promise<void> {
  setCookie(SESSION_COOKIE, await signSession(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: serverConfig.sessionTtlSeconds(),
  });
}

export function clearSessionCookie(): void {
  setCookie(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: 0,
  });
}

export async function readSession(): Promise<AdminSession | null> {
  return verifySession(getCookie(SESSION_COOKIE));
}

export function hasRank(session: AdminSession, minimum: BackendRole): boolean {
  return ROLE_RANK[session.role] >= ROLE_RANK[minimum];
}
```

### C4 — `src/lib/api/business-api.ts` (new)

```ts
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import type { BackendRole } from "./session";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Query string params. undefined/null entries are dropped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  /** Injected as X-Role. Resolved from the session by authedMiddleware — never from the client. */
  role: BackendRole;
};

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${serverConfig.businessApiUrl()}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Server-only HTTP client for business-api.
 *
 * SECURITY: the sole place X-Role is ever set. The browser cannot influence it,
 * because `role` comes from the signed session cookie via authedMiddleware.
 */
export async function businessApi<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = "GET", query, body, role } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        "X-Role": role,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (cause) {
    const offline = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      offline ? 504 : 503,
      offline ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) return undefined as T;

  const raw = await response.text();

  if (!response.ok) {
    // FastAPI shape: {"detail": "..."}
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail !== undefined) detail = JSON.stringify(parsed.detail);
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "business-api returned a malformed JSON body", path);
  }
}

/** Connectivity probe for the login screen and Settings. Never throws. */
export async function businessApiHealth(): Promise<{ reachable: boolean; detail?: string }> {
  try {
    await businessApi<{ status: string }>("/health", { role: "conseiller" });
    return { reachable: true };
  } catch (error) {
    return { reachable: false, detail: (error as ApiError)?.detail ?? "unknown error" };
  }
}
```

### C5 — `src/lib/api/middleware.ts` (new)

```ts
import { createMiddleware } from "@tanstack/react-start";
import { ApiError } from "./errors";
import { hasRank, readSession, type AdminSession, type BackendRole } from "./session";

/**
 * THE security boundary.
 *
 * Per the TanStack Start authentication guide, server functions are reachable independently of
 * the route that renders them, so a beforeLoad guard is NOT sufficient. Attach this middleware
 * to every server function that touches backend data.
 */
export const authedMiddleware = createMiddleware().server(async ({ next }) => {
  const session = await readSession();
  if (!session) {
    throw new ApiError(401, "Not authenticated", "session");
  }
  return next({ context: { session } });
});

/**
 * Role-gated variant. Mirrors require_role() in business_api/security.py so the UI fails at the
 * edge with the same verdict the backend would return, instead of making a doomed round trip.
 *
 * Usage:
 *   createServerFn({ method: "POST" })
 *     .middleware([requireRole("administrateur")])
 *     .handler(async ({ context }) => { ... })
 */
export function requireRole(minimum: BackendRole) {
  return createMiddleware().server(async ({ next }) => {
    const session = await readSession();
    if (!session) throw new ApiError(401, "Not authenticated", "session");
    if (!hasRank(session, minimum)) {
      throw new ApiError(403, `requires role >= ${minimum}`, "session");
    }
    return next({ context: { session } });
  });
}

export type AuthedContext = { session: AdminSession };
```

### C6 — `src/lib/api/auth.server.ts` (new)

```ts
import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import {
  clearSessionCookie,
  readSession,
  writeSessionCookie,
  type AdminSession,
  type BackendRole,
} from "./session";

/** Equalises response time so a wrong email and a wrong password are indistinguishable. */
async function constantTimeDelay(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 120));
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<AdminSession | null> => readSession(),
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }
    return { email: data.email.trim().toLowerCase(), password: data.password };
  })
  .handler(async ({ data }): Promise<AdminSession> => {
    await constantTimeDelay();

    const expectedEmail = serverConfig.adminEmail().trim().toLowerCase();
    const expectedPassword = serverConfig.adminPassword();

    if (data.email !== expectedEmail || data.password !== expectedPassword) {
      throw new ApiError(401, "Incorrect email or password", "login");
    }

    const session: AdminSession = {
      sub: expectedEmail,
      role: serverConfig.adminRole() as BackendRole,
      exp: Math.floor(Date.now() / 1000) + serverConfig.sessionTtlSeconds(),
    };

    await writeSessionCookie(session);
    return session;
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  clearSessionCookie();
});
```

### C7 — `src/lib/nexus/query-keys.ts` (new)

```ts
/**
 * Central query-key factory. Every cookbook adds its keys here, never inline, so that
 * invalidation after a mutation is a one-liner and cache collisions are impossible.
 */
export const queryKeys = {
  session: ["session"] as const,
  health: ["health"] as const,

  advisors: {
    all: ["advisors"] as const,
    list: (includeInactive: boolean) => ["advisors", "list", { includeInactive }] as const,
    onCall: ["advisors", "on-call"] as const,
    coverage: (days: number) => ["advisors", "coverage", { days }] as const,
    schedule: (advisorId: string) => ["advisors", advisorId, "schedule"] as const,
    timeOff: (advisorId: string, upcomingOnly: boolean) =>
      ["advisors", advisorId, "time-off", { upcomingOnly }] as const,
  },

  callbacks: {
    all: ["callbacks"] as const,
    list: (status: string, overdueOnly: boolean) =>
      ["callbacks", "list", { status, overdueOnly }] as const,
    stats: ["callbacks", "stats"] as const,
    slots: (day: string | undefined) => ["callbacks", "slots", { day }] as const,
  },

  sessions: {
    detail: (sessionId: string) => ["sessions", sessionId] as const,
  },

  customers: {
    profile360: (customerId: string) => ["customers", customerId, "360"] as const,
  },

  supervision: {
    escalations: (status: string) => ["escalations", { status }] as const,
    verdicts: (sessionId: string) => ["verdicts", { sessionId }] as const,
    actions: (status: string) => ["actions", { status }] as const,
    kpis: ["kpis"] as const,
    systemOverview: ["system", "overview"] as const,
    telemetryTimeline: ["telemetry", "timeline"] as const,
    businessRules: ["reference", "business-rules"] as const,
    auditVerify: ["audit", "verify"] as const,
    integrity: ["jobs", "integrity"] as const,
  },
} as const;
```

### C8 — `src/components/nexus/states.tsx` (new)

```tsx
import { AlertTriangle, Lock, WifiOff, type LucideIcon } from "lucide-react";
import { Button, Card, Td } from "@/components/nexus/primitives";
import { errorMessage, isForbidden, isUnauthenticated } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

/* ---------- Loading ---------- */

/** One shimmering cell. Uses surface-4 (the same fill as Avatar) — no new token. */
function Shimmer({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("block h-[10px] animate-pulse rounded-r-1 bg-surface-4", className)}
    />
  );
}

/**
 * Row-level skeleton for <TableShell>. Column count must match the header so the
 * layout does not jump when real data lands.
 */
export function TableSkeleton({ columns, rows = 6 }: { columns: number; rows?: number }) {
  const widths = ["w-[60%]", "w-[35%]", "w-[45%]", "w-[30%]", "w-[50%]", "w-[40%]"];
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} aria-hidden="true">
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <Td key={columnIndex}>
              <Shimmer className={widths[columnIndex % widths.length]} />
            </Td>
          ))}
        </tr>
      ))}
      <tr className="sr-only">
        <td colSpan={columns} role="status">
          Loading
        </td>
      </tr>
    </>
  );
}

/** Block skeleton for card/chart regions. */
export function CardSkeleton({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <Card className={className}>
      <div role="status" className="flex flex-col gap-sp-5">
        <span className="sr-only">Loading</span>
        <Shimmer className="h-[14px] w-[40%]" />
        {Array.from({ length: lines }).map((_, index) => (
          <Shimmer key={index} className={index % 2 === 0 ? "w-[85%]" : "w-[65%]"} />
        ))}
      </div>
    </Card>
  );
}

/* ---------- Error ---------- */

/**
 * Structural twin of EmptyState (primitives.tsx, chapter 24) with a retry affordance.
 * Identical spacing, radii, type ramp and icon frame — only the icon and the button differ.
 */
export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const forbidden = isForbidden(error);
  const expired = isUnauthenticated(error);

  const Icon: LucideIcon = forbidden ? Lock : expired ? Lock : WifiOff;
  const heading = title ?? (forbidden ? "Access denied" : expired ? "Session expired" : "Could not load");

  return (
    <div className="flex h-full flex-col items-center justify-center px-sp-8 py-sp-12 text-center">
      <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
        <Icon size={18} strokeWidth={1.5} />
      </span>
      <p className="t-title-3 text-ink-1">{heading}</p>
      <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">{errorMessage(error)}</p>
      {onRetry && !forbidden && !expired ? (
        <Button variant="secondary" size="sm" className="mt-sp-6" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
      {expired ? (
        <Button variant="primary" size="sm" className="mt-sp-6" onClick={() => window.location.assign("/login")}>
          Sign in
        </Button>
      ) : null}
    </div>
  );
}

/** Error state sized to sit inside a <TableShell> body. */
export function TableErrorRow({
  columns,
  error,
  onRetry,
}: {
  columns: number;
  error: unknown;
  onRetry?: () => void;
}) {
  return (
    <tr>
      <td colSpan={columns} className="border-b border-stroke-subtle">
        <ErrorState error={error} onRetry={onRetry} />
      </td>
    </tr>
  );
}

/** Inline banner for non-blocking failures (e.g. a background refetch failed). */
export function InlineError({ error }: { error: unknown }) {
  return (
    <span className="inline-flex items-center gap-sp-2 t-caption text-ink-3">
      <AlertTriangle size={12} strokeWidth={1.5} aria-hidden="true" />
      {errorMessage(error)}
    </span>
  );
}
```

### C9 — `src/routes/login.tsx` (new)

```tsx
import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { LogIn } from "lucide-react";
import { Button, Card, TextField } from "@/components/nexus/primitives";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Nexus" },
      { name: "description", content: "Authenticate to the Nexus admin console." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login({ data: { email, password } });
      await router.invalidate();
      await router.navigate({ to: "/overview" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[380px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
            <LogIn size={18} strokeWidth={1.5} />
          </span>
          <h1 className="t-title-3 text-ink-1">Nexus</h1>
          <p className="t-caption mt-sp-2 text-ink-4">Sign in to the admin console.</p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-sp-5">
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
```

### M5 — `src/components/nexus/primitives.tsx` (append at end of file)

```tsx
/* ---------- Text field (chapter 17 — same field metrics as SearchInput) ---------- */

export function TextField({
  label,
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className={cn("block", className)}>
      <span className="t-micro mb-sp-2 block font-medium text-ink-5">{label}</span>
      <input
        className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
        {...rest}
      />
    </label>
  );
}
```

> **Design-drift note.** The `className` above is copied verbatim from the `<input>` inside the
> existing `SearchInput`, with only the search-icon left padding (`pl-[30px]`) swapped for the
> standard `px-sp-5`. The label uses `t-micro`/`text-ink-5`, matching `Th`. No new token.

### M1 — `src/router.tsx` (replace whole file)

```tsx
import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { isForbidden, isUnauthenticated } from "./lib/api/errors";
import type { AdminSession } from "./lib/api/session";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Supervision data is near-real-time but not live; 30 s avoids hammering business-api
        // while keeping the console usefully fresh.
        staleTime: 30_000,
        retry: (failureCount, error) => {
          // Never retry an auth verdict — it will not change without user action.
          if (isUnauthenticated(error) || isForbidden(error)) return false;
          return failureCount < 2;
        },
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient, session: null as AdminSession | null },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
```

### M2 — `src/routes/__root.tsx` (targeted edits)

**Edit 1 — imports.** Add below the existing imports:

```tsx
import { redirect, useRouterState } from "@tanstack/react-router";
import { getSession } from "@/lib/api/auth.server";
import type { AdminSession } from "@/lib/api/session";
```

**Edit 2 — route context type and gate.** Replace:

```tsx
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
```

with:

```tsx
export const Route = createRootRouteWithContext<{
  queryClient: QueryClient;
  session: AdminSession | null;
}>()({
  // UX gate only. The security boundary is authedMiddleware on each server function
  // (see src/lib/api/middleware.ts).
  beforeLoad: async ({ location }) => {
    const session = await getSession();
    if (!session && location.pathname !== "/login") {
      throw redirect({ to: "/login" });
    }
    if (session && location.pathname === "/login") {
      throw redirect({ to: "/overview" });
    }
    return { session };
  },
  head: () => ({
```

**Edit 3 — render login without the shell.** Replace the whole `RootComponent` function with:

```tsx
function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  // The login screen is full-bleed: no sidebar, no topbar.
  if (pathname === "/login") {
    return (
      <QueryClientProvider client={queryClient}>
        <Outlet />
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AppSidebar />
      <AppShell>
        {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
        <Outlet />
      </AppShell>
    </QueryClientProvider>
  );
}
```

### M3 — `src/lib/nexus/nav.ts` (replace the trailing `ACCOUNT` block)

Replace:

```ts
export const ACCOUNT = {
  name: "Chouaib Saad",
  role: "Administrator",
  email: "chouaib.saad@nexus.io",
  initials: "CS",
};
```

with:

```ts
// Account is now derived from the signed session (see src/lib/api/session.ts).
// The shape is preserved so consuming components did not need restructuring.
export type AccountInfo = {
  name: string;
  role: string;
  email: string;
  initials: string;
};

/** Rendered only before the session resolves, and on the login screen. */
export const ACCOUNT_FALLBACK: AccountInfo = {
  name: "—",
  role: "—",
  email: "",
  initials: "··",
};
```

> **PAGE_META gap (deliberate, flagged).** `PAGE_META` has no `/login` entry, so the topbar would
> show the fallback title. This is harmless because the login route never renders the topbar
> (M2, edit 3). No entry added — adding one would be dead config.

### M4 — `src/components/nexus/app-topbar.tsx` (targeted edits)

**Edit 1 — imports.** Replace:

```tsx
import { PAGE_META, ACCOUNT } from "@/lib/nexus/nav";
import { Avatar, IconButton, SearchInput } from "@/components/nexus/primitives";
```

with:

```tsx
import { useRouter } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import { PAGE_META, ACCOUNT_FALLBACK, type AccountInfo } from "@/lib/nexus/nav";
import { Avatar, IconButton, SearchInput } from "@/components/nexus/primitives";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import { logout } from "@/lib/api/auth.server";
import { initials as toInitials } from "@/lib/nexus/format";
```

**Edit 2 — derive the account.** Inside `AppTopbar`, immediately after the existing
`const pathname = ...` line, add:

```tsx
  const router = useRouter();
  const { session } = RootRoute.useRouteContext();

  const account: AccountInfo = session
    ? {
        // No display-name field exists on the session; the local part of the email is the
        // closest honest label. See §8.1 — a real user record would supply a full name.
        name: session.sub.split("@")[0] ?? session.sub,
        role: ROLE_LABEL[session.role],
        email: session.sub,
        initials: toInitials((session.sub.split("@")[0] ?? "").replace(/[._-]/g, " ")) || "··",
      }
    : ACCOUNT_FALLBACK;

  async function onSignOut() {
    await logout();
    await router.invalidate();
    await router.navigate({ to: "/login" });
  }
```

**Edit 3 — render.** Replace:

```tsx
        <IconButton label="Notifications" icon={Bell} />
        <Avatar initials={ACCOUNT.initials} name={ACCOUNT.name} size="sm" />
```

with:

```tsx
        <IconButton label="Notifications" icon={Bell} />
        <span className="hidden flex-col items-end leading-tight md:flex">
          <span className="t-label text-ink-2">{account.name}</span>
          <span className="t-micro text-ink-4">{account.role}</span>
        </span>
        <Avatar initials={account.initials} name={account.name} size="sm" />
        <IconButton label="Sign out" icon={LogOut} onClick={onSignOut} />
```

### `.env.example` (new, at `Frontend/admin_dashboard/.env.example`)

```bash
# ---------------------------------------------------------------------------
# Admin dashboard — SERVER-SIDE ONLY.
# Do NOT prefix any of these with VITE_: the Lovable vite preset injects VITE_*
# into the client bundle, which would leak the backend URL and the secrets.
# ---------------------------------------------------------------------------

# business-api origin, reachable from the dashboard's server process.
# docker compose: http://business-api:8108
BUSINESS_API_URL=http://localhost:8108
BUSINESS_API_TIMEOUT_MS=15000

# Session cookie signing key. Generate with: openssl rand -hex 32
ADMIN_SESSION_SECRET=change-me-to-a-32-byte-hex-string

# Seeded admin credentials (stop-gap until OIDC — see cookbook §8.1).
ADMIN_EMAIL=admin@nexus.io
ADMIN_PASSWORD=change-me

# Backend role granted on login: conseiller | superviseur | administrateur
ADMIN_ROLE=administrateur

# Session lifetime in seconds (28800 = 8 h).
ADMIN_SESSION_TTL=28800
```

> Also append `.env` to `Frontend/admin_dashboard/.gitignore` if it is not already covered.

### Reference usage — the pattern every later cookbook copies

Not a file to create; this is the template Cookbook 1 will instantiate.

```ts
// src/lib/api/advisors.server.ts   (Cookbook 1 — shown here only as the canonical shape)
import { createServerFn } from "@tanstack/react-start";
import { authedMiddleware } from "./middleware";
import { businessApi } from "./business-api";

export const fetchAdvisors = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .inputValidator((data: { includeInactive?: boolean }) => ({
    includeInactive: Boolean(data?.includeInactive),
  }))
  .handler(async ({ data, context }) =>
    businessApi<{ advisors: unknown[] }>("/api/v1/advisors", {
      role: context.session.role,
      query: { include_inactive: data.includeInactive },
    }),
  );
```

```tsx
// In the route component
const { data, isPending, isError, error, refetch } = useQuery({
  queryKey: queryKeys.advisors.list(false),
  queryFn: () => fetchAdvisors({ data: { includeInactive: false } }),
});
```

---

## 7. Validation checklist

### 7.1 Build & static

- [ ] `bun install` — lockfile unchanged (zero new dependencies).
- [ ] `bun run lint` — clean.
- [ ] `bun run build` — succeeds.
- [ ] `routeTree.gen.ts` diff contains **only** the added `/login` route.

### 7.2 Transport

- [ ] With `business-api` **stopped**, the dashboard renders `ErrorState` ("Could not reach the service"), not a white screen.
- [ ] With it **running**, `businessApiHealth()` returns `{ reachable: true }`.
- [ ] Browser devtools → Network: **no request to `:8108`**. Only same-origin `/_serverFn/*`.
- [ ] Browser devtools → Network: **no `X-Role` header** on any browser request.
- [ ] `grep -r "8108" Frontend/admin_dashboard/src` returns hits only in `config.ts`.

### 7.3 Authentication

- [ ] Visiting `/overview` while signed out redirects to `/login`.
- [ ] Wrong password → "Incorrect email or password"; no session cookie is set.
- [ ] Correct credentials → redirect to `/overview`; topbar shows the real email-derived name and role.
- [ ] Cookie `nexus_admin_session` is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
- [ ] `document.cookie` in the console does **not** reveal the session.
- [ ] Tampering with one character of the cookie value forces a redirect to `/login`.
- [ ] Sign out clears the cookie and returns to `/login`.
- [ ] Visiting `/login` while signed in redirects to `/overview`.

### 7.4 Authorization boundary — the important one

- [ ] **Direct RPC replay while signed out fails.** With cookies cleared, POST directly to a server function endpoint and confirm 401 rather than data. This proves the boundary is the middleware, not `beforeLoad`.
- [ ] With `ADMIN_ROLE=conseiller`, a `requireRole("administrateur")` function returns 403 and the UI shows "Access denied".

### 7.5 Design integrity

- [ ] `git diff src/styles.css` is **empty** — no new tokens, colors, radii or type ramp.
- [ ] No new hex value or arbitrary Tailwind color anywhere in the diff.
- [ ] `TextField` and `SearchInput` rendered side by side are indistinguishable in height, radius, border and focus treatment.
- [ ] `ErrorState` and `EmptyState` share identical icon-frame size, margins and type ramp.
- [ ] `TableSkeleton` row height matches the real `Td` height (52 px) — no layout shift on load.
- [ ] The login card uses only `Card`, `TextField`, `Button`.

### 7.6 Backend integrity

- [ ] `git status apps/` — **no modified files**.
- [ ] `git status packages/` — **no modified files**.
- [ ] `git diff --stat` shows changes confined to `Frontend/admin_dashboard/`.
- [ ] No new Python file anywhere in the diff.
- [ ] No CORS change — `main.py` untouched.

---

## 8. Ambiguities needing your confirmation

### 8.1 BLOCKING — admin identity source

**The finding.** There is no user store anywhere in the backend for dashboard operators. There is
no users table, no password hashing, no login endpoint, and `security.py` states plainly that
*"Real identity is OIDC at integration time."* The system was designed to receive identity from an
external IdP that has not been connected.

**Why I did not build it.** A real user-management system — accounts, hashed credentials,
invitations, password reset, per-user roles — is missing *business logic*, not a missing endpoint.
Your constraint 3 says to flag that, not build it. So I did not.

**What I built instead.** Env-configured credentials validated at the frontend server edge, issuing
a signed cookie whose only payload is the role the backend already understands. This is genuine
access control: it prevents anonymous access, and it removes the forgeable-header hole entirely.

**What it honestly is not:**

| Limitation | Consequence |
|---|---|
| One shared credential per deployment | No per-person accountability |
| No user table | The audit ledger cannot attribute a dashboard action to an individual |
| Role fixed at deploy time | Cannot have a supervisor and an admin signed in simultaneously |
| No password rotation, lockout or MFA | Not sufficient for internet exposure |

**Please choose:**

- **(A)** Accept the stop-gap as specified. Recommended if the dashboard is on a private network
  and OIDC is genuinely coming.
- **(B)** Connect a real IdP now. Tell me which one and I will rewrite `session.ts` and
  `auth.server.ts` around it — the rest of the substrate is unaffected by design.
- **(C)** Treat a per-user store as an approved backend addition. I would need explicit
  authorisation, since it exceeds constraint 3.

### 8.2 Non-blocking — deployment topology

The dashboard server process must reach `business-api:8108`. I have not read
`docker-compose.yml`/`infra` closely enough to state which network it joins or whether a service
entry exists for the admin dashboard at all. **Confirm** whether it is containerised in the same
compose project. If not, `BUSINESS_API_URL` becomes a host-reachable address and this becomes an
ops task rather than a code one.

### 8.3 Non-blocking — Lovable sync

`Frontend/admin_dashboard/AGENTS.md` warns that the project syncs with Lovable and that pushed
history must not be rewritten. Feature 0 adds 9 files and modifies 5, with no renames and no
`routeTree.gen.ts` churn beyond the new route — deliberately, per
[§4.4](#44-decision-4--root-beforeload-gate-instead-of-an-_authed-layout-route). **Confirm** you
want these committed to `version_79` directly, or whether the whole integration series should land
on a `version_80` branch.

### 8.4 Non-blocking — session lifetime

Default is 8 hours with no idle timeout and no refresh. If supervisors keep the console open
across a shift boundary, they will be signed out mid-session. Say the word if you want a sliding
expiry instead.

### 8.5 Deferred — known endpoint gaps

Recorded here so they are not a surprise later. **Not** part of Feature 0:

| Nav destination | Gap | Cookbook |
|---|---|---|
| Tickets | No ticket endpoints in `business-api`. Ticketing lives behind the `ticketing-glpi` MCP server. Needs a decision: additive REST facade vs. a different access path. | Tickets |
| Knowledge Base | No knowledge endpoints in `business-api`. The knowledge service is on `:8102` and RAG on the `ai-knowledge-rag` MCP server. Likely needs a second upstream in `config.ts`. | RAG |
| Calls & Transcripts | `GET /api/v1/sessions/{id}` fetches one session. **There is no list-sessions endpoint**, so the calls table has nothing to enumerate. Will need an additive list endpoint. | Calls |
| Settings | No backing endpoints identified beyond the retention job. | Settings |

---

## Appendix A — file manifest

```
Frontend/admin_dashboard/
├── .env.example                                  NEW
├── src/
│   ├── router.tsx                                MODIFIED  (M1)
│   ├── components/nexus/
│   │   ├── app-topbar.tsx                        MODIFIED  (M4)
│   │   ├── primitives.tsx                        MODIFIED  (M5 — append TextField)
│   │   └── states.tsx                            NEW       (C8)
│   ├── lib/
│   │   ├── api/
│   │   │   ├── auth.server.ts                    NEW       (C6)
│   │   │   ├── business-api.ts                   NEW       (C4)
│   │   │   ├── config.ts                         NEW       (C2)
│   │   │   ├── errors.ts                         NEW       (C1)
│   │   │   ├── middleware.ts                     NEW       (C5)
│   │   │   └── session.ts                        NEW       (C3)
│   │   └── nexus/
│   │       ├── nav.ts                            MODIFIED  (M3)
│   │       └── query-keys.ts                     NEW       (C7)
│   └── routes/
│       ├── __root.tsx                            MODIFIED  (M2)
│       └── login.tsx                             NEW       (C9)

apps/            UNTOUCHED
packages/        UNTOUCHED
services/        UNTOUCHED
```

## Appendix B — application order

1. `.env.example`, then create your local `.env`.
2. C1 → C2 → C3 → C4 → C5 → C6 (dependency order; each imports the previous).
3. C7, C8, M5 (independent).
4. C9 (needs M5's `TextField`).
5. M1 → M2 (M2 needs the router context type from M1).
6. M3 → M4 (M4 needs M3's type).
7. Run §7 top to bottom.

**Rollback:** every change is confined to `Frontend/admin_dashboard/`. Revert with
`git checkout version_79 -- Frontend/admin_dashboard`.

## Appendix C — sources

**Repository, branch `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`:**
`apps/business-api/src/business_api/main.py` (`ff52daff`), `security.py` (`a059de0d`),
`Frontend/admin_dashboard/package.json` (`7bb3dc5d`), `vite.config.ts` (`174e074c`),
`src/router.tsx` (`3423d598`), `src/start.ts` (`6935f74e`), `src/server.ts` (`20500c7f`),
`src/routes/__root.tsx` (`c1933520`), `src/routes/advisors.tsx` (`6bdd9390`),
`src/components/nexus/primitives.tsx` (`73cce934`), `app-topbar.tsx` (`c57cdb0a`),
`src/lib/nexus/nav.ts` (`a00def32`), `status.ts` (`84449b29`), `format.ts` (`fa395653`),
`AGENTS.md` (`36eb1098`).

**TanStack documentation:**
- Server Functions — https://tanstack.com/start/v0/docs/framework/react/guide/server-functions
- Authentication — https://tanstack.com/start/v0/docs/framework/react/guide/authentication
- Authentication Server Primitives — https://tanstack.com/start/v0/docs/framework/react/guide/authentication-server-primitives
- Middleware — https://tanstack.com/start/v0/docs/framework/react/guide/middleware

## Appendix D — confidence

| Area | Confidence | Note |
|---|---|---|
| Backend endpoint inventory | **High** | Read directly from `main.py` |
| RBAC analysis | **High** | `security.py` read in full |
| No backend change required | **High** | CORS verified present; proxy makes it moot |
| Design-system fidelity | **High** | All 18 primitives enumerated; new components composed from existing tokens |
| TanStack API surface | **Medium-High** | `createServerFn`, `createMiddleware`, `getCookie`/`setCookie` confirmed in current docs. Pinned versions are `@tanstack/react-start ^1.168.32` / `react-router ^1.170.18`; if `inputValidator` errors at build time, the older spelling is `.validator()` — a one-word change in C6. |
| Auth completeness | **Low by design** | Constrained by the absent user store — see §8.1 |
