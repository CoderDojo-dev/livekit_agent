# Cookbook 11 — Customers & Customer 360

**Branch of record:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Applies to:** local working branch `version_80`
**Scope:** `Frontend/admin_dashboard/` + **two** additive backend symbols
**Route:** `/customers` (already exists in `nav.ts` — **no nav change, no `routeTree.gen.ts` change**)
**Status:** ready to implement — with **three blocking confirmations** in §0.3 and §8

---

## 0. Read this before you write a single line

### 0.1 The template page is not the feature its route name promises

This is the most important finding in this cookbook, and it inverts the obvious plan.

The route is `/customers`. The nav label is **Customers**, under `PLATFORM`. Every reasonable
assumption says: this page lists CRM customers, and the backend already has
`customer_360(customer_id)` waiting to power it.

That assumption is **wrong**. Here is the mock's own `head`, verbatim from
`Frontend/admin_dashboard/src/routes/customers.tsx` (`194319e10f1fec11698fb7abda31ca471a6844be`):

```tsx
head: () => ({
  meta: [
    { title: "Users Management — Nexus" },
    {
      name: "description",
      content: "Every account, role, invitation and access level in one monochrome table.",
    },
    { property: "og:title", content: "Users Management — Nexus" },
    { property: "og:description", content: "Manage accounts, roles and access levels." },
  ],
}),
```

And its table:

```tsx
<Th>User</Th>
<Th>Status</Th>
<Th>Role</Th>
<Th align="right">Last active</Th>
```

…with a `Invite user` primary button and a footer reading
`Showing {CUSTOMERS.length} of 18,204 users`.

This is a **workspace user-administration page**: accounts, roles, invitations, last-active
timestamps. It is not a CRM page. The variable is named `CUSTOMERS` but every column, the
title, the description, the button and the footer describe *platform users*.

### 0.2 The subject the template actually describes has zero backend

Cookbook 10 §8.3 established this and nothing since has changed it:

- There is **no user table anywhere in `packages/persistence/src/persistence/models/`**.
  `auth.py` (`269fc036`) does not provide a dashboard user store.
- Feature 0 authenticates the admin dashboard against **environment variables** —
  `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_ROLE`. One hardcoded operator. There is no second
  account, no invitation, no role assignment, no `last_active`.
- `security.py` (`a059de0d`) derives role from an `X-Role` **header**, falling back to
  `BUSINESS_API_DEFAULT_ROLE`. Roles are a request-time assertion, not stored records.

So *Users Management*, implemented literally, would require: a users table, an invitation
flow, a credential store, session tracking for `last_active`, and role persistence. That is
**new business logic end to end** — squarely forbidden by Constraint 3, which permits only
"creating access" to functionality that already exists.

### 0.3 The decision, and why it needs your sign-off

**Decision:** repurpose `/customers` to the **CRM customer registry** that the backend really
has, and delete the users-management framing entirely.

Justification, in the order that matters:

1. **The nav already says "Customers."** `nav.ts` places this route under `PLATFORM` labelled
   Customers. The nav is right; the page body drifted. Aligning the body to the nav is the
   smaller change.
2. **The backend's richest untouched domain is `crm.customers`** — the declared
   "single source of truth for identity" (`crm.py` docstring) — plus a fully-built
   `customer_360` aggregate that no page in the dashboard currently calls.
3. **Customer 360 is a dependency other cookbooks are already blocked on.** Cookbook 3
   (Callbacks) cannot offer manual booking without customer lookup; Cookbook 4 (Call logs)
   and Cookbook 5 (Tickets) both display a `customer_id` they cannot resolve to a human name.
4. Implementing the literal template would mean inventing backend behaviour — the exact thing
   Constraint 4 prohibits.

**BLOCKING CONFIRMATION 1.** This changes what the `/customers` page *is*. It is a product
decision, not a wiring decision, so I am not making it silently. If you intend the dashboard
to eventually manage platform users, that is a legitimate roadmap item — but it is a new
backend subsystem and belongs in its own cookbook, after a decision about where credentials
live. Say the word and I will write that design instead. **Everything below assumes you
approve the repurpose.**

### 0.4 Inherited law, restated

- **Constraint 1 — design system locked.** No new colours, radii, spacing, typography or
  component styles. `styles.css` is achromatic by law (`RR === GG === BB`). Every class used
  below already appears in the codebase.
- **Constraint 2 — backend core logic locked.** Nothing existing is modified. Two purely
  additive symbols only.
- **Constraint 3 — additions create access, never features.**
- **Constraint 4 — no silent assumptions.** Six items are flagged rather than guessed.
- **Chip law.** `StatusChip` does `const def = STATUS[status]; if (!def) return null;` — an
  unknown key renders **nothing at all**, silently. Ten consecutive cookbooks have shipped
  with **zero changes to `status.ts`**. This one does too, and it is the hardest case yet
  (§3.4).

---

## 1. Feature name & scope

**Customers & Customer 360** — a searchable, paginated registry of CRM customers, with a
drill-through detail panel showing the full 360 aggregate: profile, subscriptions, open
invoices and tickets.

### In scope

| Capability | Backing |
| --- | --- |
| Customer list, searchable, status-filtered, paginated | **NEW** `GET /api/v1/customers` |
| Total customer count | existing `GET /api/v1/system/overview` → `metrics.total_customers` |
| Customer 360 detail panel | existing `GET /api/v1/customers/{customer_id}/360` |
| Subscription list per customer | inside the 360 payload |
| Open invoices per customer | inside the 360 payload |
| Tickets per customer, cross-linked to `/tickets` | inside the 360 payload |

### Explicitly out of scope

| Not doing | Why |
| --- | --- |
| Create / edit / delete customers | No write endpoint exists. Customer creation is business logic (Constraint 3). |
| Invite user, roles, last-active | No backend whatsoever (§0.2). Controls removed. |
| Displaying `national_id` (CIN) | §3.1 — deliberate omission. |
| Consent records, customer interactions | `ConsentRecord` and `CustomerInteraction` exist in `crm.py` but have **no HTTP surface**. Flagged §8.6. |
| Payments, payment plans, notifications | `billing.py` models exist; no endpoints. Flagged §8.6. |

---

## 2. Backend reference — exact, verified

### 2.1 `crm.Customer` — `packages/persistence/src/persistence/models/crm.py` (`65fe123c`)

Module docstring, verbatim:

> CRM schema (spec section 4): customer identity system of record + consent/interactions.
> `crm.customers` is the single source of truth for identity; `national_id` carries the CIN
> (closing review note 4). `crm.subscriptions` owns the MSISDN as a UNIQUE attribute - never a
> join key (spec section 1).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | via `UUIDPrimaryKey` |
| `national_id` | `String(50)` NOT NULL **unique** | **the CIN.** Never rendered — §3.1 |
| `first_name` | `String(100)` NOT NULL | |
| `last_name` | `String(100)` NOT NULL | |
| `email` | `String(255)` unique, **nullable** | |
| `contact_number` | `String(20)` nullable | masked in UI |
| `preferred_language` | `String(10)` NOT NULL, default `'fr'` | CHECK `IN ('fr','ar','en')` |
| `segment` | `String(80)` nullable, indexed | free-form |
| `vip_flag` | `Boolean` NOT NULL default false | |
| `fraud_suspected` | `Boolean` NOT NULL default false | sensitive — §8.4 |
| `address` | `Text` nullable | not rendered |
| `city` | `String(100)` nullable | |
| `region` | `String(100)` nullable | |
| `status` | `String(20)` NOT NULL default `'active'`, indexed | CHECK `IN ('active','suspended','closed')` |
| `glpi_user_id` | `Integer` nullable, unique, indexed | ties to Cookbook 5 |

Mixins: `UUIDPrimaryKey, Timestamps, SoftDelete, Base`. **`SoftDelete` matters — see §3.5.**

### 2.2 `crm.Subscription`

| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | UUID FK → `crm.customers.id` `ondelete=RESTRICT` | indexed |
| `msisdn` | `String(20)` NOT NULL **unique** | "UNIQUE attribute, never an FK" |
| `plan_type` | `String(20)` NOT NULL | CHECK `IN ('PREPAID','POSTPAID')` — **uppercase** |
| `plan_code` | `String(50)` nullable | |
| `status` | `String(20)` NOT NULL default `'ACTIVE'` | CHECK `IN ('ACTIVE','SUSPENDED','BLOCKED','TERMINATED')` — **uppercase** |
| `roaming_enabled` | `Boolean` NOT NULL default false | |
| `activation_date` | `Date` nullable | |

Also `SoftDelete`.

### 2.3 `billing.Invoice` — `billing.py` (`2ce40c1f`, read for the first time in this cookbook)

| Column | Type | Notes |
| --- | --- | --- |
| `account_id` | UUID FK → `billing.accounts.id` | |
| `customer_id` | UUID FK → `crm.customers.id` | indexed |
| `invoice_number` | `String(40)` NOT NULL unique | |
| `period_start` / `period_end` / `issue_date` / `due_date` | `Date` NOT NULL | |
| `subtotal` / `tax_amount` / `total_amount` / `outstanding_amount` | `Numeric(12,2)` NOT NULL default 0 | **decimal units, not cents** — §3.3 |
| `currency_code` | `String(3)` NOT NULL default `'TND'` | |
| `status` | `String(20)` NOT NULL default `'issued'`, indexed | CHECK `IN ('draft','issued','paid','partial','overdue','disputed','void')` |

This **closes Cookbook 9 §8.3's open question** about invoice status values. The answer is
seven values, of which `status.ts` knows only three.

Note `Invoice` has `Timestamps` but **not** `SoftDelete`.

### 2.4 `SupervisionRepository.customer_360(customer_id)` — `repositories.py` (`0f9acd1f`)

Return shape:

```python
{
  "customer_id": ...,
  "name": ...,                  # first_name + last_name
  "vip": ...,                   # from vip_flag
  "preferred_language": ...,
  "subscriptions": [{"subscription_id", "msisdn", "plan", "status"}],
  "open_invoices": [{"invoice", "amount", "status"}],   # only where i.status != "paid"
  "tickets":       [{"glpi_id", "status", "subject"}],
}
```

Returns `None` when the customer does not exist.

**Note what is absent:** `status`, `email`, `contact_number`, `segment`, `fraud_suspected`,
`city`, `region`, `glpi_user_id`. The 360 aggregate is deliberately narrow. This directly
shapes the design — see §3.2.

### 2.5 `GET /api/v1/customers/{customer_id}/360` — `main.py` (`ff52daff`)

```python
@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data
```

- Role gate: **`ConseillerRole`** — the lowest rank. Any authenticated role reaches it.
- Returns the aggregate **flat**, with no envelope — like `/kpis`, unlike every list route.
- `customer_id: str` — **no UUID validation.** See §3.6.

### 2.6 There is no list endpoint. At all.

I walked all 34 routes in `main.py`. The only customer route is the 360 above. There is **no**
`GET /api/v1/customers`, no search, no count-by-status.

This is the hard blocker: **the 360 endpoint requires a UUID you have no way to obtain.**
Nothing in the dashboard can produce a customer id — `/calls` and `/tickets` carry
`customer_id` values, but the registry page has no entry point at all. Without a list
endpoint this page cannot render a single row.

---

## 3. Findings that shape the implementation

### F1 — This is the most PII-dense table in the system (§3.1)

`crm.customers` holds, per row: full legal name, **national identity number (CIN)**, email,
phone, and postal address. The system takes this seriously elsewhere — there is a dedicated
`packages/pii-shield`, and `audit.pii_token_map` (`audit.py`, `08aab975`) tokenizes exactly
`'msisdn','national_id','email','name','iccid'` with `encrypted_value LargeBinary`.

So the platform's own design treats `national_id` as something to tokenize and encrypt.
A dashboard table that prints it in plaintext, 25 rows at a time, in a browser, over an
admin session, would defeat that design.

**Decision:** `national_id` is **not selected by the new query**. Not fetched, not
serialised, not sent to the browser. You cannot leak a column you never read. Search does
not match against it either.

**Consequence, stated plainly:** an operator cannot look a customer up by CIN. For a telecom
back office that may be a real workflow. I am not deciding it away — see §8.1.

### F2 — The 360 payload cannot fill the columns the page needs (§3.2)

The list needs `status` (the mock has a Status column, and CRM status is genuinely useful).
`customer_360` does not return `status`. Nor email, nor phone.

So the split is:

- **List endpoint** supplies everything the *table* shows: name, email, masked phone, status,
  language, VIP, segment.
- **360 endpoint** supplies everything the *panel* shows: subscriptions, invoices, tickets.

The panel therefore reuses the row's own data for the header (name, status, VIP) and calls
360 only for the three collections. This avoids adding fields to `customer_360` — which would
modify existing behaviour and breach Constraint 2.

### F3 — `formatCurrency` will silently render wrong money (§3.3)

`format.ts` (`fa395653`) exports `formatCurrency(cents)`. Its parameter is **cents**.

`Invoice.total_amount` is `Numeric(12, 2)` — a decimal amount in whole currency units. An
invoice of `120.50` TND passed to `formatCurrency` renders as **1.21**, not 120.50. Off by
two orders of magnitude, and plausible enough that nobody notices.

Second problem: the currency is **TND** (`currency_code` defaults to `'TND'` on both `Account`
and `Invoice`), while `format.ts` pins `LOCALE = "en-US"`.

**Decision:** do not use `formatCurrency` here. `customer-view.ts` defines `formatAmount`,
which takes a decimal number and a currency code and never assumes cents. This is a *new
helper*, not a new style — no visual token changes.

### F4 — Chip trap, ninth recurrence, and the worst one yet (§3.4)

Three status vocabularies collide on this single page. `status.ts` (`84449b29`) is the
canonical truth table — *"No status exists outside it."*

**Customer status** — `active | suspended | closed`
All three exist in `status.ts`. **First backend vocabulary in eleven cookbooks that maps 1:1.**
Pass through unchanged; still route it through a mapper so the guarantee is enforced in code.

**Subscription status** — `ACTIVE | SUSPENDED | BLOCKED | TERMINATED`
Uppercase, and two values are unknown to `status.ts`. Naively passing `"ACTIVE"` yields
`STATUS["ACTIVE"] === undefined` → **the chip renders nothing**. Mapping:

| Backend | → `status.ts` | Reasoning |
| --- | --- | --- |
| `ACTIVE` | `active` | exact |
| `SUSPENDED` | `suspended` | exact |
| `BLOCKED` | `disabled` | a blocked line is administratively disabled, not closed |
| `TERMINATED` | `closed` | terminal end-of-life, matching customer `closed` |

**Invoice status** — `draft | issued | paid | partial | overdue | disputed | void`
`status.ts` has `draft`, `paid`, `overdue`. Four are missing. Mapping:

| Backend | → `status.ts` | Reasoning |
| --- | --- | --- |
| `draft` | `draft` | exact |
| `issued` | `pending` | issued and awaiting payment |
| `paid` | `paid` | exact — though filtered out of `open_invoices` |
| `partial` | `in_progress` | partially settled, work ongoing |
| `overdue` | `overdue` | exact |
| `disputed` | `escalated` | matches C8's use of `escalated` for contested outcomes |
| `void` | `archived` | cancelled, retained for record |

`paid` is included for completeness even though `customer_360` filters `i.status != "paid"` —
if that filter ever changes, the chip already works.

**Not chips:** `vip_flag` is boolean → a `Token strong` reading `VIP`, rendered only when
true. `preferred_language` (`fr|ar|en`) → a plain `Token`. `plan_type` (`PREPAID|POSTPAID`) →
a plain `Token`. None of these are statuses and none get a chip.

### F5 — `SoftDelete` must be honoured, and I cannot guess the column (§3.5)

`Customer` and `Subscription` both mix in `SoftDelete` from `persistence.base`. A list query
that ignores it will show deleted customers as live records.

**I have not read `packages/persistence/src/persistence/base.py`.** I do not know whether the
mixin's field is `deleted_at`, `is_deleted`, or something else, and I will not guess a column
name into a query. §5.1 marks the exact line and gives the command to resolve it.

Note: it is also unknown whether the existing `customer_360` filters soft-deleted rows. If it
does not, that is a pre-existing gap — **do not fix it here** (Constraint 2); record it.

### F6 — `customer_id: str` with no UUID validation is a 500, not a 404 (§3.6)

`customer_360(customer_id: str, ...)` accepts any string and passes it into a query against a
`UUID` column. A malformed value does not produce the intended 404 — Postgres raises
`invalid input syntax for type uuid`, surfacing as an unhandled **500**.

Same family as the `max_frustration` 500 from Cookbook 4. The UI never constructs ids by hand
— they come only from list rows — so the frontend does not trigger it. But it is reachable by
hand and worth recording. Guard drafted in §8.5, **not shipped** (Constraint 2).

### F7 — Inert controls, and the fabricated 18,204

The mock's `Filter` button, `Invite user` button, `Previous`/`Next` buttons and
select-all/per-row `Checkbox`es have no handlers. The footer count `18,204` is invented.

Per the Feature 5 precedent — **remove, don't disable**:

- `Invite user` — **removed.** No backend; creating customers is business logic.
- Checkboxes — **removed.** Multi-select exists to serve a bulk action; there are no bulk
  endpoints, so selection would lead nowhere.
- `Filter` button — **replaced** by a real `Segmented` status filter.
- `Previous`/`Next` — **wired** to real offset pagination.
- `18,204` — replaced with the real total.

### F8 — Two call-site checks inherited from earlier cookbooks

1. **`SearchInput` may not forward `value`/`onChange`.** Feature 1 hit this. `primitives.tsx`
   declares `SearchInput({ placeholder, className })` — the destructured signature suggests
   other props are dropped. §5.2 gives the check and both branches.
2. **`Td` may not forward `colSpan`.** Needed for full-width skeleton/error/empty rows.
   Same check, same fallback (plain `<td>`).

### F9 — Search must be server-side and debounced

With `total_customers` potentially large, client-side filtering of a 25-row page is
meaningless. Search goes to the backend as a query param, debounced at 300 ms, and resets
`offset` to 0 on every change — otherwise you land on page 4 of a 1-page result and see
nothing.

### F10 — `refetchOnWindowFocus: true` is fine here

Unlike Cookbook 10 — where `verify()` rehashes the entire audit ledger and re-running it on
every tab-focus was unacceptable — these are ordinary indexed reads. Standard `useQuery` with
the global `staleTime: 30_000` is correct. No mutations, because there are no writes.

### F11 — Reuse, don't redefine

`format.ts` already exports `initials(name)` and `maskPhone`. `Avatar` already takes
`initials` + `name`. Cookbook 9 already made `delta` **optional** on `HeroStat`/`StatCard` —
which this page depends on, because there is no historical customer series to compute a delta
from. Cookbook 1's `Modal` already portals to `document.body`, which is mandatory here
because `PageSection` carries `.rise` (`transform: translateY(8px)`), creating a containing
block that clips any `position: fixed` descendant.

---

## 4. Endpoints

### 4.1 Existing — reused unchanged

| Method | Path | Role | Used for |
| --- | --- | --- | --- |
| `GET` | `/api/v1/customers/{customer_id}/360` | conseiller | Detail panel |
| `GET` | `/api/v1/system/overview` | superviseur | `metrics.total_customers` |

### 4.2 New — additive only

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/customers` | conseiller | Paginated, searchable customer registry |

**Why this is access, not a feature.** It is a read over an existing table with no derived
business meaning — the same justification accepted for `session_list` (C4),
`decision_ledger` (C8), `analytics_trend` (C9) and `audit_entries` (C10). The repository
docstring already scopes it: *"Read-side queries for the supervision endpoints (spec section
17). Read-only; never mutates audit."*

**Role choice.** `ConseillerRole`, matching the 360 endpoint. Rationale: an advisor on a live
call must identify the caller, and gating the list above the detail would be incoherent —
anyone who can read a customer should be able to find one. **Counter-argument:** listing the
whole registry is a broader capability than fetching one known id, and this table is PII-dense
(F1). See §8.2.

#### Contract

```
GET /api/v1/customers?search=&status=&limit=25&offset=0
```

| Param | Type | Default | Behaviour |
| --- | --- | --- | --- |
| `search` | str | `""` | Case-insensitive match on first name, last name, email, phone. **Never `national_id`.** Empty = no filter. |
| `status` | str | `""` | Exact match on `crm.customers.status`. Empty = all. |
| `limit` | int | 25 | Clamped 1–100 |
| `offset` | int | 0 | Clamped ≥ 0 |

Empty-filter convention: **`""` means "no filter"** — matching Cookbook 3 (`status=""` = All).
Recorded because it varies per cookbook: C5 omits the param entirely, C8 omits empty params,
C9 whitelists.

Response — enveloped, matching every other list route:

```json
{
  "customers": [
    {
      "customer_id": "8f...",
      "name": "Amina Ben Salah",
      "email": "amina@example.tn",
      "contact_number": "+21620123456",
      "preferred_language": "fr",
      "segment": "consumer",
      "vip": false,
      "fraud_suspected": false,
      "status": "active",
      "city": "Tunis"
    }
  ],
  "total": 18204,
  "limit": 25,
  "offset": 0
}
```

`total` is the count **after** filters, so pagination is correct under search.

---

## 5. Backend implementation

### 5.1 `apps/business-api/src/business_api/repositories.py` — add one method

Append inside `SupervisionRepository`, immediately **after** `customer_360` so related reads
stay together.

> **`import os` is not needed here.** (C9 and C10 both had to add it; this one does not.)
> `func` and `select` are already imported in this module.

```python
    def customer_list(
        self,
        search: str = "",
        status: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """Paginated CRM registry for the admin dashboard (read-only).

        Deliberately does not select ``national_id``: the CIN is tokenised elsewhere
        (audit.pii_token_map) and must never reach a browser. Search therefore matches
        name / email / phone only.
        """
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))

        conditions = []
        # !!! SOFT DELETE — resolve before applying, see note below.
        # conditions.append(Customer.<soft_delete_column>.is_(None))

        if status:
            conditions.append(Customer.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Customer.first_name.ilike(pattern),
                    Customer.last_name.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.contact_number.ilike(pattern),
                )
            )

        total = self._session.scalar(
            select(func.count()).select_from(Customer).where(*conditions)
        ) or 0

        rows = self._session.scalars(
            select(Customer)
            .where(*conditions)
            .order_by(Customer.last_name.asc(), Customer.first_name.asc())
            .limit(limit)
            .offset(offset)
        ).all()

        return {
            "customers": [
                {
                    "customer_id": str(c.id),
                    "name": f"{c.first_name} {c.last_name}".strip(),
                    "email": c.email,
                    "contact_number": c.contact_number,
                    "preferred_language": c.preferred_language,
                    "segment": c.segment,
                    "vip": bool(c.vip_flag),
                    "fraud_suspected": bool(c.fraud_suspected),
                    "status": c.status,
                    "city": c.city,
                }
                for c in rows
            ],
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }
```

**Import additions at the top of the file:**

- `or_` must be added to the existing `from sqlalchemy import ...` line.
- `Customer` must be imported from the persistence models if it is not already present
  (`customer_360` uses it, so it almost certainly is — **verify, do not assume**).

**MUST RESOLVE — the soft-delete line.** Before applying, run:

```bash
grep -n "class SoftDelete" -A 10 packages/persistence/src/persistence/base.py
```

Uncomment the condition and substitute the real column. If the mixin uses a boolean
(`is_deleted`), the condition becomes `Customer.is_deleted.is_(False)` instead. **Do not apply
this method with that line still commented out** — you would list deleted customers as live.

**Ordering choice:** `last_name, first_name` ascending — stable and human-meaningful. Do not
order by `created_at`; there is no product reason and it makes offset pagination
counter-intuitive under search.

**Why offset and not keyset:** the UI needs a total and jumpable pages; the table is indexed
and modest; C10's keyset choice was driven by the audit ledger's strict `seq` ordering, which
has no analogue here.

### 5.2 `apps/business-api/src/business_api/main.py` — add one route

Insert **immediately before** the existing `customer_360` route, so FastAPI matches the
collection path before the parameterised one and the two customer routes read together.

> This mirrors the existing comment in the advisors block: *"Coverage must be declared BEFORE
> {advisor_id} routes so FastAPI doesn't route 'coverage' as an id."* Here the paths do not
> actually collide (`/customers` vs `/customers/{id}/360`), so ordering is for readability,
> not correctness.

```python
@app.get("/api/v1/customers")
def list_customers(
    session: DbSession,
    role: ConseillerRole,
    search: str = "",
    status: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """Paginated CRM customer registry (admin dashboard lookup)."""
    return SupervisionRepository(session).customer_list(search, status, limit, offset)
```

No new imports. No CORS change — `CORS_ORIGINS` and the allowed headers
(`Content-Type`, `X-Role`) already cover this, and Feature 0 routes everything through the
TanStack server proxy anyway, so the browser never talks to `:8108` directly.

**Nothing else in `main.py` is touched.**

---

## 6. Frontend implementation

### 6.1 File manifest

| Action | Path |
| --- | --- |
| **NEW** | `src/lib/api/customers.server.ts` |
| **NEW** | `src/lib/nexus/customer-view.ts` |
| **NEW** | `src/components/nexus/customer-detail.tsx` |
| **MOD** | `src/lib/nexus/query-keys.ts` (+`customerKeys`) |
| **MOD** | `src/lib/nexus/data.ts` (−`CUSTOMER_STATS`, −`CustomerRow`, −`CUSTOMERS`) |
| **REWRITE** | `src/routes/customers.tsx` |

**No `nav.ts` change. No `routeTree.gen.ts` change. No `status.ts` change. No new npm
dependency. No new design token.**

### 6.2 `src/lib/api/customers.server.ts`

All reads. Per Feature 2's CSRF finding, mutating server functions must be
`createServerFn({ method: "POST" })` — **there are no mutations here**, so every function is a
`GET`.

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/client";
import { authedMiddleware, inputValidator, requireRole } from "@/lib/api/middleware";

export type CustomerRow = {
  customer_id: string;
  name: string;
  email: string | null;
  contact_number: string | null;
  preferred_language: string;
  segment: string | null;
  vip: boolean;
  fraud_suspected: boolean;
  status: string;
  city: string | null;
};

export type CustomerPage = {
  customers: CustomerRow[];
  total: number;
  limit: number;
  offset: number;
};

export type CustomerSubscription = {
  subscription_id: string;
  msisdn: string;
  plan: string;
  status: string;
};

export type CustomerInvoice = {
  invoice: string;
  amount: number;
  status: string;
};

export type CustomerTicket = {
  glpi_id: number | string;
  status: string;
  subject: string;
};

export type Customer360 = {
  customer_id: string;
  name: string;
  vip: boolean;
  preferred_language: string;
  subscriptions: CustomerSubscription[];
  open_invoices: CustomerInvoice[];
  tickets: CustomerTicket[];
};

const listInput = z.object({
  search: z.string().max(120).default(""),
  status: z.enum(["", "active", "suspended", "closed"]).default(""),
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().min(0).default(0),
});

export const listCustomers = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator(inputValidator(listInput))
  .handler(async ({ data, context }) => {
    return businessApi<CustomerPage>("/api/v1/customers", {
      method: "GET",
      query: {
        search: data.search,
        status: data.status,
        limit: data.limit,
        offset: data.offset,
      },
      role: context.session.role,
    });
  });

const detailInput = z.object({
  customerId: z.string().uuid(),
});

export const getCustomer360 = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator(inputValidator(detailInput))
  .handler(async ({ data, context }) => {
    return businessApi<Customer360>(
      `/api/v1/customers/${encodeURIComponent(data.customerId)}/360`,
      { method: "GET", role: context.session.role },
    );
  });
```

Three deliberate choices:

1. **`z.string().uuid()` on the detail input.** This is the frontend-side answer to F6: a
   malformed id is rejected at the server function boundary and never reaches the backend's
   unguarded `str` param. It costs nothing and closes the 500 from this direction — without
   modifying backend code.
2. **`status` is a `z.enum`,** not a free string. The three values come straight from the
   `CheckConstraint`. An invalid status cannot be sent.
3. **`requireRole("conseiller")` is called as a factory** — Feature 2 correction #2. It is
   `requireRole(minimum)`, not a bare middleware.

### 6.3 `src/lib/nexus/customer-view.ts`

Pure functions. No JSX, no colours, no dates parsed from strings.

```ts
import type { StatusKey } from "@/lib/nexus/status";

/** crm.customers.status -> canonical key. All three already exist in status.ts. */
export function customerStatusKey(status: string): StatusKey | null {
  switch (status) {
    case "active":
      return "active";
    case "suspended":
      return "suspended";
    case "closed":
      return "closed";
    default:
      return null;
  }
}

/** crm.subscriptions.status is UPPERCASE and has two keys status.ts does not know. */
export function subscriptionStatusKey(status: string): StatusKey | null {
  switch (status?.toUpperCase()) {
    case "ACTIVE":
      return "active";
    case "SUSPENDED":
      return "suspended";
    case "BLOCKED":
      return "disabled";
    case "TERMINATED":
      return "closed";
    default:
      return null;
  }
}

/** billing.invoices.status has seven values; status.ts knows three. */
export function invoiceStatusKey(status: string): StatusKey | null {
  switch (status?.toLowerCase()) {
    case "draft":
      return "draft";
    case "issued":
      return "pending";
    case "paid":
      return "paid";
    case "partial":
      return "in_progress";
    case "overdue":
      return "overdue";
    case "disputed":
      return "escalated";
    case "void":
      return "archived";
    default:
      return null;
  }
}

const LANGUAGE_LABEL: Record<string, string> = {
  fr: "FR",
  ar: "AR",
  en: "EN",
};

export function languageLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return LANGUAGE_LABEL[code.toLowerCase()] ?? code.toUpperCase();
}

/**
 * Money formatter for billing amounts.
 *
 * Deliberately NOT format.ts `formatCurrency`, which expects CENTS. Invoice amounts are
 * Numeric(12,2) decimal units, so formatCurrency would render 120.50 TND as 1.21.
 */
export function formatAmount(amount: number, currency = "TND"): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return "—";
  return `${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

/** Inclusive 1-based range for the footer, correct on the final partial page. */
export function pageRange(
  offset: number,
  limit: number,
  total: number,
): { from: number; to: number } {
  if (total === 0) return { from: 0, to: 0 };
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return { from, to };
}

export function hasPrevious(offset: number): boolean {
  return offset > 0;
}

export function hasNext(offset: number, limit: number, total: number): boolean {
  return offset + limit < total;
}

/** Sum of open invoice amounts, for the panel's summary line. */
export function outstandingTotal(invoices: Array<{ amount: number }>): number {
  return invoices.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
}
```

Note `formatAmount` uses `toLocaleString("en-US", …)` on a **number** — a numeric formatter,
not a date one. The date-trap rule bans `new Date` parsing and `getDay`/`getHours`; there are
no dates on this page at all.

> **Consistency note.** `format.ts` already exports `formatInteger` with `LOCALE = "en-US"`.
> Use `formatInteger` for the customer counts in the footer and stat cards rather than calling
> `toLocaleString` again — this is the same duplication I flagged at the end of Cookbook 10,
> and it should not be repeated here.

### 6.4 `src/lib/nexus/query-keys.ts` — add

```ts
export const customerKeys = {
  all: ["customers"] as const,
  list: (search: string, status: string, limit: number, offset: number) =>
    ["customers", "list", search, status, limit, offset] as const,
  detail: (customerId: string) => ["customers", "detail", customerId] as const,
};
```

Every filter is part of the list key, so paging and searching cache independently and going
back a page is instant.

### 6.5 `src/components/nexus/customer-detail.tsx`

The 360 panel. Rendered inside the existing `Modal`, which **portals to `document.body`** —
mandatory, per Feature 1 defect #3, because `PageSection` has `.rise`
(`transform: translateY(8px)`) and any `position: fixed` descendant would be clipped to it.

```tsx
import { useQuery } from "@tanstack/react-query";
import { Modal } from "@/components/nexus/modal";
import { StatusChip, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { EmptyState } from "@/components/nexus/primitives";
import { getCustomer360, type CustomerRow } from "@/lib/api/customers.server";
import { customerKeys } from "@/lib/nexus/query-keys";
import {
  formatAmount,
  invoiceStatusKey,
  languageLabel,
  outstandingTotal,
  subscriptionStatusKey,
} from "@/lib/nexus/customer-view";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { maskPhone } from "@/lib/nexus/format";

type Props = {
  customer: CustomerRow | null;
  onClose: () => void;
};

export function CustomerDetail({ customer, onClose }: Props) {
  const enabled = Boolean(customer);

  const query = useQuery({
    queryKey: customerKeys.detail(customer?.customer_id ?? ""),
    queryFn: () =>
      getCustomer360({ data: { customerId: customer!.customer_id } }),
    enabled,
  });

  if (!customer) return null;

  const notFound = isApiError(query.error) && query.error.status === 404;

  return (
    <Modal open onClose={onClose} title={customer.name}>
      {/* Header strip — from the row, because customer_360 omits status/email/phone */}
      <div className="flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle pb-sp-5">
        <StatusChip status={customer.status} />
        {customer.vip ? <Token strong>VIP</Token> : null}
        <Token mono={false}>{languageLabel(customer.preferred_language)}</Token>
        {customer.segment ? <Token mono={false}>{customer.segment}</Token> : null}
        <span className="t-caption ml-auto text-ink-4">
          {customer.email ?? "—"}
          {customer.contact_number ? ` · ${maskPhone(customer.contact_number)}` : ""}
        </span>
      </div>

      {query.isPending ? (
        <div className="mt-sp-7">
          <CardSkeleton />
        </div>
      ) : notFound ? (
        <div className="mt-sp-7">
          <EmptyState
            title="Customer no longer available"
            description="This record was removed after the list was loaded. Refresh the table."
          />
        </div>
      ) : query.isError ? (
        <div className="mt-sp-7">
          <ErrorState
            message={errorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        </div>
      ) : (
        <>
          {/* Subscriptions */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Subscriptions</h3>
            {query.data!.subscriptions.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">No subscriptions on record.</p>
            ) : (
              <ul className="mt-sp-5">
                {query.data!.subscriptions.map((s) => (
                  <li
                    key={s.subscription_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <span className="min-w-0">
                      <span className="t-ui truncate text-ink-1">{s.msisdn}</span>
                      <span className="t-caption truncate text-ink-4">{s.plan}</span>
                    </span>
                    <span className="ml-auto">
                      <StatusChip status={subscriptionStatusKey(s.status) ?? ""} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Open invoices */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Open invoices</h3>
            {query.data!.open_invoices.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">Nothing outstanding.</p>
            ) : (
              <>
                <ul className="mt-sp-5">
                  {query.data!.open_invoices.map((inv) => (
                    <li
                      key={inv.invoice}
                      className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                    >
                      <span className="t-ui truncate text-ink-1">{inv.invoice}</span>
                      <span className="ml-auto flex items-center gap-sp-5">
                        <span className="t-mono-l text-ink-1">
                          {formatAmount(inv.amount)}
                        </span>
                        <StatusChip status={invoiceStatusKey(inv.status) ?? ""} />
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="mt-sp-6 flex items-center border-t border-stroke-subtle pt-sp-5">
                  <span className="t-label text-ink-3">Total outstanding</span>
                  <span className="t-mono-l ml-auto text-ink-1">
                    {formatAmount(outstandingTotal(query.data!.open_invoices))}
                  </span>
                </div>
              </>
            )}
          </section>

          {/* Tickets */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Tickets</h3>
            {query.data!.tickets.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">No tickets raised.</p>
            ) : (
              <ul className="mt-sp-5">
                {query.data!.tickets.map((t) => (
                  <li
                    key={String(t.glpi_id)}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <span className="min-w-0">
                      <span className="t-ui truncate text-ink-1">{t.subject}</span>
                      <span className="t-caption truncate text-ink-4">#{t.glpi_id}</span>
                    </span>
                    <span className="ml-auto">
                      <StatusChip status={t.status} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Modal>
  );
}
```

**On the ticket chip:** `customer_360` returns the GLPI status verbatim. Cookbook 5 already
solved this mapping for `/tickets`. **Import Cookbook 5's mapper rather than re-deriving it** —
the same reuse discipline Cookbook 9 applied by importing Feature 1's `advisor-view.ts`
instead of re-deriving advisor status. If C5's `ticket-view.ts` is not yet applied on your
branch, the raw value flows through and an unmapped status renders no chip — visible in
testing, and resolved when C5 lands. Recorded in §7.

### 6.6 `src/routes/customers.tsx` — full rewrite

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { CustomerDetail } from "@/components/nexus/customer-detail";
import { listCustomers, type CustomerRow } from "@/lib/api/customers.server";
import { getSystemOverview } from "@/lib/api/analytics.server";
import { customerKeys, analyticsKeys } from "@/lib/nexus/query-keys";
import {
  customerStatusKey,
  hasNext,
  hasPrevious,
  languageLabel,
  pageRange,
} from "@/lib/nexus/customer-view";
import { errorMessage } from "@/lib/api/errors";
import { formatInteger, initials, maskPhone } from "@/lib/nexus/format";
import { useDebounced } from "@/hooks/use-debounced";

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Suspended", value: "suspended" },
  { label: "Closed", value: "closed" },
] as const;

export const Route = createFileRoute("/customers")({
  head: () => ({
    meta: [
      { title: "Customers — Nexus" },
      {
        name: "description",
        content:
          "The CRM registry: identity, subscriptions, open invoices and tickets per customer.",
      },
      { property: "og:title", content: "Customers — Nexus" },
      {
        property: "og:description",
        content: "Look up a customer and open their full 360 record.",
      },
    ],
  }),
  component: CustomersPage,
});

function CustomersPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CustomerRow | null>(null);

  const debouncedSearch = useDebounced(search, 300);

  const list = useQuery({
    queryKey: customerKeys.list(debouncedSearch, status, PAGE_SIZE, offset),
    queryFn: () =>
      listCustomers({
        data: { search: debouncedSearch, status, limit: PAGE_SIZE, offset },
      }),
    placeholderData: keepPreviousData,
  });

  const overview = useQuery({
    queryKey: analyticsKeys.system,
    queryFn: () => getSystemOverview(),
  });

  const rows = list.data?.customers ?? [];
  const total = list.data?.total ?? 0;
  const range = pageRange(offset, PAGE_SIZE, total);

  const filtering = debouncedSearch !== "" || status !== "";

  function changeSearch(value: string) {
    setSearch(value);
    setOffset(0);
  }

  function changeStatus(value: string) {
    setStatus(value);
    setOffset(0);
  }

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <HeroStat
          label="Customers"
          value={
            overview.data
              ? formatInteger(overview.data.metrics.total_customers)
              : "—"
          }
          context="Identity records in crm.customers"
        />
        <StatCard
          label={filtering ? "Matching" : "Listed"}
          value={list.data ? formatInteger(total) : "—"}
          context={filtering ? "Rows matching the current filters" : "All customers"}
        />
        <StatCard
          label="Subscriptions"
          value="—"
          context="Open a customer to see their lines"
        />
        <StatCard
          label="Page"
          value={total === 0 ? "0" : `${range.from}–${range.to}`}
          context={`${PAGE_SIZE} per page`}
        />
      </PageSection>

      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput
                placeholder="Search name, email or phone"
                className="w-[280px]"
                value={search}
                onChange={(e) => changeSearch(e.target.value)}
              />
              <Segmented
                options={STATUS_OPTIONS.map((o) => o.label)}
                value={
                  STATUS_OPTIONS.find((o) => o.value === status)?.label ?? "All"
                }
                onChange={(label: string) =>
                  changeStatus(
                    STATUS_OPTIONS.find((o) => o.label === label)?.value ?? "",
                  )
                }
              />
            </>
          }
          head={
            <tr>
              <Th>Customer</Th>
              <Th>Status</Th>
              <Th>Language</Th>
              <Th>Segment</Th>
              <Th align="right">Phone</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                {total === 0
                  ? "No customers"
                  : `Showing ${range.from}–${range.to} of ${formatInteger(total)}`}
              </span>
              <div className="flex gap-sp-4">
                <Button
                  size="sm"
                  disabled={!hasPrevious(offset) || list.isPending}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={!hasNext(offset, PAGE_SIZE, total) || list.isPending}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </>
          }
        >
          {list.isPending ? (
            <TableSkeleton rows={8} cols={5} />
          ) : list.isError ? (
            <TableErrorRow
              colSpan={5}
              message={errorMessage(list.error)}
              onRetry={() => list.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={5}>
                <EmptyState
                  title={filtering ? "No matching customers" : "No customers yet"}
                  description={
                    filtering
                      ? "Adjust the search term or status filter."
                      : "The CRM registry is empty."
                  }
                />
              </td>
            </tr>
          ) : (
            rows.map((c) => (
              <tr
                key={c.customer_id}
                onClick={() => setSelected(c)}
                className="cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <Td>
                  <span className="flex items-center gap-sp-5">
                    <Avatar initials={initials(c.name)} name={c.name} />
                    <span className="min-w-0">
                      <span className="t-ui block truncate text-ink-1">
                        {c.name}
                        {c.vip ? " " : ""}
                        {c.vip ? <Token strong>VIP</Token> : null}
                      </span>
                      <span className="t-caption block truncate text-ink-4">
                        {c.email ?? "—"}
                      </span>
                    </span>
                  </span>
                </Td>
                <Td>
                  <StatusChip status={customerStatusKey(c.status) ?? ""} />
                </Td>
                <Td>
                  <Token mono={false}>{languageLabel(c.preferred_language)}</Token>
                </Td>
                <Td>
                  <span className="t-caption text-ink-4">{c.segment ?? "—"}</span>
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">
                    {c.contact_number ? maskPhone(c.contact_number) : "—"}
                  </span>
                </Td>
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>

      <CustomerDetail customer={selected} onClose={() => setSelected(null)} />
    </>
  );
}
```

#### Notes on the rewrite

- **`keepPreviousData`** keeps the current page visible while the next one loads, so paging
  and typing do not flash a skeleton over the whole table.
- **`useDebounced`** — `src/hooks/` has **not been read** (outstanding since Phase 1). If no
  such hook exists, add a five-line local one; do **not** pull in a dependency. Zero new npm
  packages is a standing invariant. Flagged §7.
- **The `Subscriptions` stat card shows `—` by design.** There is no endpoint that counts
  subscriptions across customers, and `system_overview()`'s metrics do not include one
  (`total_calls, total_turns, total_verdicts, total_actions, total_audit_entries,
  total_customers, total_escalations`). Rather than invent a number, the card states where
  the data actually lives. Alternative in §8.3.
- **`delta` is omitted** on `HeroStat` and both `StatCard`s — possible only because Cookbook 9
  made it optional. If C9 is not applied on your branch, this page will not compile. Hard
  dependency, §7.
- **`fraud_suspected` is fetched but not rendered.** See §8.4 before deciding to surface it.

---

## 7. Dependencies and ordering

| Depends on | Why | Hard? |
| --- | --- | --- |
| **Feature 0** | `businessApi`, `authedMiddleware`, `requireRole`, `inputValidator`, `errorMessage`, `isApiError`, states | **Hard** |
| **Feature 1** | `Modal` (portals to `document.body`), `Segmented` `type="button"` fix, `errorMessage` string branch | **Hard** |
| **Cookbook 9** | optional `delta` on `HeroStat`/`StatCard`; `getSystemOverview`; `analyticsKeys.system` | **Hard — will not compile without it** |
| **Cookbook 5** | `ticket-view.ts` status mapper for the panel's ticket chips | Soft — degrades to a missing chip |
| `src/hooks/use-debounced` | search debounce | Soft — trivially inlined |

**Unblocks:** Cookbook 3's manual callback booking, which has been waiting on
`GET /api/v1/customers?search=`. Once this ships, C3 §8's open item can close.

---

## 8. Open questions — your call

### 8.1 Should CIN (`national_id`) lookup be possible? *(blocking for search UX)*

I excluded it entirely (F1). For a telecom back office, "customer walks in with their ID
card" is a plausible primary workflow. If you need it, the safest shape is **exact-match
only, never prefix or `ILIKE`, never returned in the response** — you can search *by* CIN but
the column is never rendered. Say so and I will specify it precisely.

### 8.2 Is `conseiller` the right gate for the full registry?

The 360 endpoint is `conseiller`, so I matched it. But *listing* every customer is a broader
capability than fetching one known record, and this is the most PII-dense table in the
system. `superviseur` for the list while leaving 360 at `conseiller` is defensible — an
advisor resolves the caller in front of them, a supervisor browses. Your call; it is a
one-word change.

### 8.3 The empty "Subscriptions" stat card

Three options: (a) leave it as the pointer it is; (b) drop the card and run a three-card row;
(c) add a `total_subscriptions` count. Option (c) means touching `system_overview()` — an
existing method — so it needs your approval under Constraint 2. I lean (b): an em-dash card
is honest but it is also dead space.

### 8.4 Should `fraud_suspected` be visible?

It is fetched and unused. Arguments to show it: an advisor should know before making
concessions. Arguments against: it is an accusation, unexplained and unsourced in the schema,
visible to the lowest role. If you want it, I would restrict it to `superviseur`+ and render
it as a subtle marker, never a red flag — the design system is achromatic anyway.

### 8.5 The `customer_id` 500 (F6)

Backend guard, **not shipped** because it changes existing behaviour:

```python
@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    try:
        uuid.UUID(customer_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="customer not found")
    ...
```

The frontend already blocks this path via `z.string().uuid()`, so this is defence in depth
for other callers. Note this is now the **second** known unguarded 500 in `main.py`,
alongside Cookbook 4's `float(call.max_frustration_score)` on a nullable column — which is
still unfixed and now reachable from four directions.

### 8.6 CRM and billing tables with no HTTP surface

Reading `crm.py` and `billing.py` in full surfaced substantial modelled data that nothing
exposes: `ConsentRecord`, `CustomerInteraction`, `Payment`, `PaymentPlan`,
`billing.Notification`, `InvoiceItem`, `Account`. `CustomerInteraction` in particular
(`channel`, `detected_intent`, `resolution`, `summary`) reads like a ready-made per-customer
history tab.

Each would need a new read endpoint. That is more than "one feature" and I am not smuggling
it in. Flagging it as the clearest candidate for the next cookbook if you want to go deeper
on customers rather than broader across the dashboard.

### 8.7 What is `amount` in `open_invoices`?

`customer_360` maps invoices to `{invoice, amount, status}`. `billing.Invoice` has **both**
`total_amount` and `outstanding_amount`. Which one feeds `amount` determines whether
"Total outstanding" in the panel is truthful or overstated on partially-paid invoices.

I labelled the column neutrally ("Amount") and the sum "Total outstanding" — which is correct
if it is `outstanding_amount` and **misleading if it is `total_amount`**. Resolve with:

```bash
grep -n "open_invoices" -B 5 -A 15 apps/business-api/src/business_api/repositories.py
```

If it is `total_amount`, rename the summary line to "Total invoiced". **Do not ship the
summary line until this is confirmed** — a wrong money label is worse than no label.

---

## 9. Validation checklist

### 9.1 Before writing code

- [ ] §0.3 confirmed: `/customers` becomes the CRM registry.
- [ ] `SoftDelete` column resolved (§5.1) and the condition uncommented.
- [ ] §8.7 resolved: `amount` is `outstanding_amount` or `total_amount`.
- [ ] `grep -n "Customer" apps/business-api/src/business_api/repositories.py | head` — confirm
      `Customer` is already imported.
- [ ] `grep -rn "CUSTOMER_STATS\|CUSTOMERS\b\|CustomerRow" Frontend/admin_dashboard/src/` —
      confirm nothing outside `customers.tsx` consumes them, **including the unread
      `src/routes/index.tsx`**, before deleting from `data.ts`.
- [ ] `ls Frontend/admin_dashboard/src/hooks/` — does `use-debounced` exist?
- [ ] Cookbook 9 applied? (`delta` optional on `HeroStat`/`StatCard`.)

### 9.2 Call-site checks (F8)

- [ ] `grep -n "function SearchInput" -A 12 src/components/nexus/primitives.tsx` — does it
      forward `value`/`onChange`? If not, extend the signature to pass them through
      (additive, no style change) rather than replacing the component.
- [ ] `grep -n "function Td" -A 8 src/components/nexus/primitives.tsx` — does it forward
      `colSpan`? The empty-state row above uses a plain `<td colSpan={5}>` to sidestep this;
      `TableErrorRow` already handles it.
- [ ] `grep -n "function Segmented" -A 15 src/components/nexus/primitives.tsx` — confirm the
      `options`/`value`/`onChange` prop names match what §6.6 assumes. Adjust the call site,
      **never the component's markup**.

### 9.3 Backend

- [ ] `GET /api/v1/customers` returns 200 with `{customers, total, limit, offset}`.
- [ ] `?limit=500` clamps to 100; `?limit=0` clamps to 1; `?offset=-5` clamps to 0.
- [ ] `?status=active` filters; `?status=` returns all.
- [ ] `?search=` matching a first name, a last name, an email and a phone each return hits.
- [ ] **`?search=<a real CIN>` returns nothing** — proving `national_id` is not searchable.
- [ ] `national_id` appears **nowhere** in the JSON response.
- [ ] `total` reflects filters, not the whole table.
- [ ] Soft-deleted customer does not appear.
- [ ] Role: `X-Role: conseiller` succeeds; check behaviour with a lower/absent role.
- [ ] `git diff --stat` on the backend touches exactly **two** files, **additive only**.

### 9.4 Frontend

- [ ] Table renders real rows; no mock names remain.
- [ ] Search debounces at ~300 ms and resets to page 1.
- [ ] Status filter resets to page 1.
- [ ] Previous disabled on page 1; Next disabled on the final page; footer range correct on a
      partial final page.
- [ ] Row click opens the panel; Escape and scrim close it.
- [ ] **Panel is not clipped** — proof that `Modal` portals to `document.body` past `.rise`.
- [ ] Every chip in the panel actually renders: force a `BLOCKED` subscription and a
      `disputed` invoice and confirm neither is blank.
- [ ] Invoice amount matches the DB value exactly — **not** off by 100× (F3).
- [ ] Customer with no subscriptions / no invoices / no tickets shows the three empty lines,
      not a broken layout.
- [ ] 404 path: delete a customer between list and click → "no longer available", not a crash.
- [ ] Phone masked in both table and panel.
- [ ] Loading, error and empty states all reachable.

### 9.5 Regression

- [ ] `tsc --noEmit` clean.
- [ ] `lint` back to exactly the **36-problem baseline** (28 prettier errors + 8 warnings).
- [ ] `build` exit 0.
- [ ] `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/customers.tsx src/components/nexus/customer-detail.tsx src/lib/nexus/customer-view.ts` → no hits.
- [ ] `grep -n 'getDay(\|getHours(\|new Date(' src/lib/nexus/customer-view.ts` → no hits.
- [ ] `git diff src/lib/nexus/status.ts` → **empty**. Eleventh consecutive cookbook.
- [ ] `git diff src/routeTree.gen.ts` → no customers line (route already existed).
- [ ] `git diff src/lib/nexus/nav.ts` → empty.
- [ ] `package.json` unchanged — zero new dependencies.
- [ ] Network tab: **zero** direct browser requests to `:8108`.
