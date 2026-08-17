# CUSTOMER PORTAL — IMPLEMENTATION COOKBOOKS (INDEX + GROUND TRUTH)

**Repository** `CoderDojo-dev/livekit_agent`
**Branch verified for this plan** `version_92` (blob SHA of the tree read: `d43726d8c77db69e3030019de079bffe11070db8`)
**Subject** `Frontend/customer_portal/` + the client-facing surface of `apps/business-api/`, plus the realtime patterns in `apps/client-widget/` and `apps/agent-worker/`.
**Status** PLAN + CODE. Nothing has been committed. Every code block below is written to be applied on the *next* branch (`version_93`) but is derived only from `version_92`.

---

## 0. How to use these cookbooks

| # | File | Needs backend? | Depends on |
|---|---|---|---|
| 1 | `01-audit-and-cleanup.md` | no | — |
| 2 | `02-api-auth-foundation.md` | no (uses shipped auth routes) | 1 |
| 3 | `03-customer-data-pages.md` | yes (additive `/api/v1/me/*`) | 2 |
| 4 | `04-ux-data-layout-revamp.md` | no | 3 (data shapes) |
| 5 | `05-orb-and-realtime-assistant.md` | token-service (1 optional additive field) + 2 new frontend deps | 2 |
| 6 | `06-tool-event-timeline.md` | no | 5 |
| 7 | `07-final-polish-and-ci.md` | no | 1–6 |

Execution order is the numeric order. Cookbooks 1 and 2 are shippable on their own and touch **no backend file at all**.

---

## 1. What was verified on `version_92` (read verbatim in this pass)

**Frontend / customer portal**
`src/routes/__root.tsx`, `_portal.tsx`, `index.tsx`, `login.tsx`, `signup.tsx`, `_portal/assistant.tsx`, `_portal/security.tsx`,
`src/components/portal/primitives.tsx`, `src/components/shell/portal-shell.tsx`, `portal-rail.tsx`, `portal-topbar.tsx`, `portal-tabbar.tsx`,
`src/components/orb/orb.tsx`, `src/lib/orb-config.ts`, `src/lib/nav.ts`, `src/lib/copy.ts`, `src/styles.css`,
`src/lib/api/*` (all 8: `auth.server.ts`, `me.server.ts`, `business-api.ts`, `session.ts`, `session.server.ts`, `middleware.ts`, `config.ts`, `errors.ts`),
`package.json`, `.env.example`. Directory listings for `routes/_portal`, `components/{orb,portal,shell,ui}`, `lib`, `lib/api`, `lib/fixtures`.

**Backend / business-api**
`main.py` (whole file), `portal_auth.py`, `repositories.py` (whole file), `infrastructure/auth/principal.py`.

**Persistence models**
`conversation.py`, `billing.py`, `ocs.py`, `ticketing.py`, `portal_identity.py` (+ the models directory listing).

**Realtime reference implementation**
`apps/client-widget/src/App.tsx`, `src/components/app/live-conversation.tsx`, `src/hooks/agents-ui/use-agent-control-bar.ts`, `src/hooks/agents-ui/use-agent-audio-visualizer-aura.ts`, `apps/client-widget/package.json`,
`apps/agent-worker/src/frontend_events.py`, `apps/token-service/src/token_service/main.py`.

**Attached design document** `CLIENT_PORTAL_cookbook.md` (written against `version_90`) was read end-to-end and used only as a checklist. Every claim it makes that these cookbooks rely on has been re-verified on `version_92`; the corrections are in §4.

---

## 2. Ground truth the whole plan rests on

### 2.1 The two mirror-image gates (`principal.py`, verified)

```python
MACHINE_ROLE = "conseiller"

@dataclass(frozen=True)
class Principal:
    subject: str
    kind: str          # "staff" | "client" | "service"
    role: str          # conseiller | superviseur | administrateur | client
    account_id: UUID | None = None
    customer_id: UUID | None = None
    session_id: UUID | None = None

def current_client(principal) -> Principal:
    if principal.kind != "client" or principal.customer_id is None:
        raise HTTPException(status_code=403, detail="requires a client account")
    return principal
```

* `current_principal` accepts a bearer token **revalidated against `auth.portal_sessions` on every request**, or `X-API-Key` pinned to `conseiller`.
* `current_client` refuses staff and machine callers. Every new client route hangs off it and reads `principal.customer_id`.
* `current_principal` depends on the **same** `get_session` callable as `DbSession`, so one request opens one connection. New routes must keep using `DbSession`.

### 2.2 What a client token can reach today (`main.py`, verified)

```
GET  /health                              (ungated)
POST /api/v1/auth/login                   (anonymous, rate bucket login:{ip}, audited auth_login)
POST /api/v1/auth/signup                  (anonymous, rate bucket signup:{ip} limit=10, audited auth_signup)
POST /api/v1/auth/logout                  (CurrentPrincipal, idempotent)
GET  /api/v1/auth/me                      (CurrentPrincipal)
POST /api/v1/auth/password                (CurrentPrincipal, 403 when account_id is None, audited)
POST /api/v1/auth/sessions/revoke-all     (CurrentPrincipal, audited)
GET  /api/v1/me/profile                   (ClientPrincipal -> customer_360)
GET  /api/v1/me/profile/detail            (ClientPrincipal -> me_profile_detail)
```

Everything else in `main.py` is `ConseillerRole` / `SuperviseurRole` / `AdministrateurRole` and is unreachable by a client, because `"client"` is absent from `_ROLE_RANK` and therefore scores rank 0.

**Login response (verified, exact keys):**
```json
{"token": "...", "expires_at": "...", "email": "...", "role": "...", "kind": "...", "customer_id": "...|null"}
```

**Auth status map (verified):**
```python
_AUTH_STATUS = {"invalid_credentials": 401, "signup_failed": 401,
                "weak_password": 400, "locked": 429, "rate_limited": 429}
```

### 2.3 Password / lockout rules (`portal_auth.py`, verified)

```python
MAX_FAILED_ATTEMPTS = 5      # override PORTAL_MAX_FAILED_ATTEMPTS
LOCKOUT_MINUTES = 15         # override PORTAL_LOCKOUT_MINUTES
MIN_PASSWORD_LENGTH = 10     # NOT 8
```
* `change_password` rejects a replacement equal to the current one (`weak_password`) and then calls `revoke_all`, returning the count.
* `signup_client` collapses every failure below the password check into one generic `signup_failed` message: *"We could not match those details to an account."* The UI must not be more helpful than that.
* A **suspended** subscription can still sign in; only `deleted_at` or `customer.status == "closed"` is refused.

### 2.4 Repository facts that decide the backend work (`repositories.py`, verified — this is the B‑1 preflight, answered)

| Question | Verified answer | Consequence |
|---|---|---|
| Does `customer_360` include subscriptions/plan? | **Yes** — `subscriptions[{subscription_id, msisdn, plan, status}]`, `open_invoices[{invoice, amount, outstanding, status}]` (unpaid only), `tickets[{glpi_id, status, subject}]` | Services “YOUR PLAN” needs **no new endpoint**; use the shipped `/api/v1/me/profile`. |
| Does `session_list` filter by customer? | **Yes** — `customer_id: str \| None` parameter | but its projection leaks `max_frustration`, `recording_consent`, `has_recording` → **do not reuse for a client**. |
| Does `ticket_list` filter by customer? | **Yes** — `customer_id: str \| None` | projection includes `customer_vip`, `last_synced_at` → new narrow projection for the client. |
| Does `notification_list` filter by customer? | **No** — deliberately unscoped, and it returns `failure_reason` | new narrow customer-scoped read required. |
| Is there an OCS balance read? | **Yes** — `customer_service_actions` reads `ocs.BalanceAccount` scoped through the customer’s subscriptions | prepaid Billing is buildable **without** inventing anything. |
| What does `session_detail` return? | `disposition`, `duration_seconds`, `max_frustration`, `turns[{index, speaker, agent, text}]`, `sentiment[{index, score, label}]` | sentiment + frustration are internal → new narrow transcript projection. |
| Does `customer_ledger` return invoices? | **No** — `payments`, `payment_plans`, `consents` only (invoice *numbers* joined onto payments) | an invoice list needs a new narrow read over `billing.Invoice`. |

House limits to reuse rather than reinvent: `_LEDGER_LIMIT = 50`, `_SERVICE_LIMIT = 50`, `_NOTIFICATION_LIMIT_MAX = 200`, `ticket_list`/`session_list` clamp at 200, `reference_catalog` clamps at 500.

### 2.5 Column-level truth used by the new reads (models, verified)

* `conversation.call_sessions`: `customer_id?`, `subscription_id?`, `msisdn?`, `channel`, `livekit_room?`, `start_time`, `end_time?`, `duration_seconds?`, `final_disposition?` ∈ {resolved, escalated, dropped, abandoned}, `max_frustration_score`, `recording_consent?`, `audio_record_url?`, `created_at`.
* `conversation.turns`: `session_id`, `turn_index`, `speaker` ∈ {caller, agent}, `active_agent?`, `detected_language?`, `transcript_masked?`, `detected_intent?`, `created_at`; unique `(session_id, turn_index, speaker)`.
* `conversation.callback_schedules`: `customer_id?`, `scheduled_time`, `priority_level`, `status` ∈ {pending, completed, cancelled}, `preferred_window?`, `reason?`, `attempts`, `outcome_note?`, `completed_at?`.
* `ticketing.tickets`: `glpi_ticket_id`, `category` ∈ {network_complaint, formal_complaint, technical, billing, other}, `subject?`, `status` ∈ {open, in_progress, **pending**, resolved, closed}, `priority?`, `last_synced_at`, `created_at`.
* `billing.accounts`: `account_number`, `account_type` ∈ {postpaid, hybrid}, `billing_cycle_day`, `payment_terms_days`, `currency_code` default **TND**, `status`.
* `billing.invoices`: `invoice_number`, `period_start/end`, `issue_date`, `due_date`, `subtotal`, `tax_amount`, `total_amount`, `outstanding_amount`, `currency_code`, `status` ∈ {draft, issued, paid, partial, overdue, disputed, void}.
* `billing.notifications`: `customer_id?`, `channel` ∈ {sms, whatsapp, email}, `template_code?`, `status` ∈ {queued, sent, failed}, `failure_reason?` (only when failed), `sent_at?`, `created_at`. **No read/unread column exists.**
* `ocs.balance_accounts`: `balance_type` ∈ {main, data, voice, sms}, `balance_value` `Numeric(14,4)`, `balance_unit` ∈ {TND, GB, MB, MIN, SMS}, `expiry_date?`, `status` ∈ {active, expired, suspended}; unique `(subscription_id, balance_type)`.
* `ocs.recharges`: `amount`, `bonus_amount`, `channel` ∈ {app, web, ussd, scratch_card, agent}, `transaction_reference?`, `status` ∈ {pending, completed, failed}, `created_at`.
* `auth.portal_accounts`: `kind`, `email`, `role`, `customer_id?`, `is_active`, `failed_attempts`, `locked_until?`, `last_login_at?`, `password_changed_at?`.
* `auth.portal_sessions`: `account_id`, `token_digest` (**never expose**), `expires_at`, `revoked_at?`, `ip_address?` (45), `user_agent?` (200), plus the `Timestamps` mixin.

### 2.6 Design identity (verified from `styles.css` + `primitives.tsx`)

13 greys `--n-0…--n-12`; surfaces `--surface-0…5`; strokes subtle/default/strong/ink; inks `--ink-1…5` + `--ink-inverse`; spacing `--sp-1…12` (2→80 px); **radius ceiling `--r-5` = 12 px**; elevations `--elev-0…4`; glows soft/strong/line; z-layers incl. **`--z-callbar: 40`**; durations `--d-1…9` (80→900 ms); easings out/in/out-soft/in-out; 18 type utilities (`t-display`, `t-metric-xl/l/m`, `t-title-1/2/3`, `t-body`, `t-body-strong`, `t-ui`, `t-ui-regular`, `t-label`, `t-caption`, `t-micro`, `t-micro-2`, `t-mono`, `t-mono-s`, `t-mono-l`); `focus-ring`; `hatch-45`; a `.skeleton` class with a `shimmer` keyframe; a `caret` keyframe (**declared but unused today**); the `body::after` grain at `--z-grain: 9999`; and a global `prefers-reduced-motion` block forcing 0.001 ms.

Primitive catalogue (exact props): `Button{variant: primary|secondary|ghost|quiet|danger, size: sm|md|lg}`, `IconButton{label}`, `Card{inset=true}`, `SectionLabel{children, right?}`, `StatusChip{tone: solid|outline|dashed|dotted|muted}`, `Divider`, `FieldRow{label, value, hint?, action?, mono?}`, `SwitchRow{label, description, checked, onChange}`, `Meter{label, used, limit, unit}`, `EmptyState{title, body, action?}`, `Tabs{tabs:{id,label}[], value, onChange}`, `SearchField{placeholder, value, onChange, className?}`, `Segmented{options, value, onChange, label}`.

Available animation dependency: **`motion` ^12.43.0 is already in the portal `package.json`** — the same package the client-widget uses (`motion/react`). Cookbook 4 therefore needs **no new dependency**.

### 2.7 Realtime truth (verified)

* `token-service` (`:8107`): `POST /token {room, identity, name}` → `{token, url, room, agent_name}`, TTL **15 min**, grants `room_join` only, sets attribute `telecom.caller_msisdn` **from the `PILOT_MSISDN` env var only**, dispatches the agent named by `LIVEKIT_AGENT_NAME`; `POST /client-events` mirrors browser events to logs; CORS default `http://localhost:5173`.
* `apps/agent-worker/src/frontend_events.py` publishes, on LiveKit text-stream topic **`telecom.tool-events`**, exactly:
  ```json
  {"version":1,"kind":"tool","id":"<call_id>","name":"<tool_name>","label":"<safe label>","status":"done|error","created_at":<number>}
  ```
  with a 15-entry label map (`knowledge_search`→“Searching telecom knowledge”, `get_invoice_summary`→“Reading invoice information”, `get_balance_summary`→“Reading account balance”, `get_plan_details`→“Reading plan details”, `route_to_billing`, `route_to_technical`, `escalate_to_manager`, `verify_with_known_element`, `record_consent`, `change_plan`, `execute_payment`, `unblock_sim`, `replace_sim`, `create_ticket`, `schedule_callback`). Arguments and outputs are deliberately never published.
* `apps/client-widget` uses `livekit-client ^2.20.1` + `@livekit/components-react ^2.9.23` with `TokenSource.custom`, `useSession`, `AgentSessionProvider`, `useSessionContext`, `useAgent`, `useTranscriptions`, `useTextStream`, `useTrackToggle`, `useTrackVolume`, `StartAudioButton`.
* LiveKit `AgentState` values observed in client-widget code: `disconnected`, `connecting`, `pre-connect-buffering`, `initializing`, `idle`, `listening`, `thinking`, `speaking`, `failed` — a **9-state machine that matches the orb’s 9 states one-for-one** (`preConnect` ↔ `pre-connect-buffering`).

---

## 3. Non-negotiable rules for every cookbook

1. **Gate every new client route with `ClientPrincipal`**; read `customer_id` from the principal, never from path/query/body.
2. Any `{id}` path parameter is attacker-supplied: re-check ownership inside the handler and return **404** (not 403) on a miss.
3. Use `DbSession`; never open a second session.
4. **Append only.** No existing handler, repository method, model, or migration is edited. New reads live in a **new module** (`me_reads.py`) so `repositories.py` is never opened.
5. Never widen `customer_360`, `me_profile_detail`, `session_detail`, `ticket_list`, `notification_list`, `customer_service_actions`.
6. Read-only: no `POST/PATCH/PUT/DELETE` beyond the three auth writes that already exist.
7. Do not audit read paths.
8. No migration. No model change. `"client"` stays out of `_ROLE_RANK`; `security.py` and `principal.py` are not opened.
9. Frontend: only `@/components/portal/primitives`; no `@/components/ui/*`; never import from `Frontend/admin_dashboard`.
10. No hex colour, no raw `box-shadow`, no font-size literal, no radius above `r-5`, no hue on the orb (`vec3(l)` stays achromatic).
11. Every visible string goes in `src/lib/copy.ts` (the file’s own rule: *“Aucune chaine visible n’est ecrite dans un composant”*).
12. Money is **TND**; times are `Africa/Tunis`; server-formatted strings are rendered as-is.

---

## 4. Corrections to the attached `version_90` document, verified on `version_92`

| Attached doc says | `version_92` reality | Effect |
|---|---|---|
| “B‑7 prepaid balance is an honest unknown; may not exist” | `customer_service_actions` **already reads `ocs.BalanceAccount`** (and `Recharge`, `PlanChangeHistory`, `SimOrder`, `ProvisioningRequest`) scoped by the customer’s subscriptions | Prepaid Billing is fully buildable. B‑7 is **not** blocked. |
| “B‑1: check whether `customer_360` carries plan data” | It does: `subscriptions[]` with `msisdn`, `plan`, `status` | Services plan section needs **no endpoint**. |
| “`customer_ledger` probably returns invoices” | It returns payments / payment_plans / consents **only** | Invoice list needs a new narrow read (provided in Cookbook 3). |
| “`notification_list` — verify scoping” | Explicitly **not** customer-scoped, and exposes `failure_reason` | New narrow customer-scoped read (provided). |
| “`copy.requests.status` maps 4 statuses” | The DB allows **5** (`pending` missing from the map) | Cookbook 3 adds the missing key. |
| “eleven destinations” in `nav.ts` / `portal-rail.tsx` | `NAV` holds **ten** (3+3+4), `PAGE_HEAD` holds ten, `routes/_portal/` holds ten files | Comment fix in Cookbook 1. |
| “no LiveKit client anywhere in the portal” | Confirmed: portal `package.json` has **no** `livekit-*`; `motion ^12.43.0` **is** present | Cookbook 5 adds exactly two deps; Cookbook 4 adds none. |
| “Option C blocked on reading the token service” | Token service **read**: `POST /token` works, but the caller MSISDN comes only from `PILOT_MSISDN` | Cookbook 5 carries one optional additive field (`caller_msisdn`) as a decision gate. |

---

## 5. Verification gates to run **before** applying any cookbook (cheap, mandatory)

From the repository root on the target branch:

```sh
# 1. Confirm the role table still excludes "client" (rule 8).
git grep -n "_ROLE_RANK" -- apps/business-api/src/business_api/security.py

# 2. Confirm no portal file imports the shadcn residue or the admin tree (rule 9).
git grep -n "@/components/ui/"      -- Frontend/customer_portal/src
git grep -n "admin_dashboard"        -- Frontend/customer_portal/src
git grep -n "use-mobile"             -- Frontend/customer_portal/src

# 3. Confirm which files still import fixtures (Cookbook 1 deletion order).
git grep -n "lib/fixtures"           -- Frontend/customer_portal/src

# 4. Confirm the Timestamps mixin columns used by /me/sessions.
sed -n '1,80p' packages/persistence/src/persistence/base.py

# 5. Confirm the Alembic head has not moved (no migration is allowed).
ls packages/persistence/alembic/versions | tail -n 3
```

Record the output of gates 1–3 in the PR body. If gate 1 shows `"client"` inside `_ROLE_RANK`, **stop**: the security model has changed and these cookbooks must be re-derived.

---

## 6. Deliberate blind spots (not read in this pass — no claims made about them)

`routes/_portal/{activity,requests,services,billing,help,profile,preferences,about}.tsx` bodies (their data wiring is known from the attached doc and from the fixture imports, but their exact JSX was not re-read on `version_92`), all six `lib/fixtures/*`, all 46 `components/ui/*` bodies, `components/orb/orb-renderer.ts` body (its public API `setState`/`setLevel`/`destroy` **is** verified through `orb.tsx`), `orb-plinth.tsx`, `lib/{utils,error-capture,error-page,lovable-error-reporting}.ts`, `router.tsx`, `server.ts`, `start.ts`, `routeTree.gen.ts`, `hooks/use-mobile.tsx`, `vite.config.ts`, `Frontend/admin_dashboard/**`, `apps/client-widget/src/components/agents-ui/*` bodies, `apps/business-api/src/business_api/{advisors,availability,callbacks,kpis,policy_view,security,seed_admin}.py`, `api/`, `application/`, `infrastructure/` (except `auth/principal.py`), `jobs/`.

Wherever a cookbook step touches one of these, it is written as **“open the file, then apply this exact edit”** with a grep gate, never as a blind rewrite.
