# FEATURE_16 — Customer ledger: payments, deferral plans & consent

> Branch of truth: `version_81` @ `2f10a07` (GitHub). Operator local HEAD: `f584eef` (FEATURE_15 applied, unpushed).
> Scope: **admin dashboard only**. Backend change is **additive-only** (one new repository method + one new GET route).
> Design system: **locked**. Every class string in this document is copied from an existing file, cited inline.

---

## 1. Feature name & scope

**Customer ledger** — surface the money and consent evidence that the backend already writes for a
customer but which no admin screen can currently read:

| Surfaced | Backend table | Written by |
| --- | --- | --- |
| Payments | `billing.payments` | `services/execution-service/src/execution_service/projections.py::_payment` |
| Deferral plans | `billing.payment_plans` | `services/execution-service/src/execution_service/projections.py::_payment_plan` |
| Consent captures | `crm.consent_records` | `apps/agent-worker/src/conversation/writer.py` (kind `"consent"`) |

**Placement:** three new read-only `<section>` blocks appended inside the existing customer 360 modal
(`components/nexus/customer-detail.tsx`), below the existing *Subscriptions / Open invoices / Tickets*
sections. No new route, no new nav entry, no new page.

### In scope
- One new additive endpoint `GET /api/v1/customers/{customer_id}/ledger`.
- One new repository method `SupervisionRepository.customer_ledger()`.
- One new server function, one new query key, three new view mappers, three new UI sections.
- One new pytest contract test.

### Explicitly OUT of scope — and why

**`crm.CustomerInteraction` is excluded.** `search_code` across `version_81` returns **two** hits for
`CustomerInteraction`: the model definition in `packages/persistence/src/persistence/models/crm.py`, and a
stale duplicate under `patches/persistance_p1/` (not the live tree). **Nothing anywhere in the repository
constructs or inserts a `CustomerInteraction` row.** The table is empty by construction and will remain so.

Under **HARD CONSTRAINT 3** this is not "a feature missing an endpoint" — it is *missing business logic*.
Exposing it would require me to write the interaction-recording write path (a hook in
`apps/agent-worker/src/conversation/writer.py` or a projection in `projections.py`), which is building a
feature, not creating access. **Flagged, not built.** See §6.A for the go/no-go.

Also out of scope (candidate FEATURE_17, "service action history"): `billing.Account`,
`billing.Notification`, `ocs.Recharge`, `sim.BlockUnblockCase`, `provisioning.{ProvisioningRequest,
SimOrder, PlanChangeHistory}` — all genuinely written by `projections.py`, all unexposed, all belonging to a
different narrative (service actions, not money).

### Honest data-state disclosure (read this before testing)

`execution.action_ledger` currently holds **0 rows** in the local database (`answers.md`, verified v80).
`_payment` and `_payment_plan` only run as projections of an **AUTHORIZED** execution, inside a SAVEPOINT of
the execute transaction. Therefore `billing.payments` and `billing.payment_plans` are almost certainly
**empty in the current dev DB**.

This is an **empty-for-data reasons** state, not empty-for-design. The write logic is real and reachable —
unlike `CustomerInteraction`. The empty states in §4 are worded to say exactly that, so the operator is never
left wondering whether the wiring is broken. `crm.consent_records` is written per-call by the agent worker
and is the collection most likely to show real rows today.

---

## 2. Backend reference (existing, verified at `2f10a07`)

### 2.1 Models

`packages/persistence/src/persistence/models/billing.py` — module docstring already anticipates this:
> *"Payments / payment_plans (write paths) land with the execution-service persistence slice."*

```
Payment(UUIDPrimaryKey, Timestamps)      -> billing.payments
  account_id, invoice_id (nullable), customer_id,
  amount Numeric(12,2), currency_code, method (card|bank_transfer|wallet|voucher|cash),
  gateway_reference, idempotency_key (unique),
  status (pending|succeeded|failed|refunded), paid_at

PaymentPlan(UUIDPrimaryKey, Timestamps)  -> billing.payment_plans
  account_id, customer_id, total_amount, installment_count (1-12),
  installment_amount, deferral_until (Date),
  status (proposed|active|completed|defaulted|cancelled),
  policy_verdict_id (loose reference, NOT a foreign key)

Invoice                                   -> billing.invoices
  ... invoice_number ...   (used here only to resolve Payment.invoice_id -> a human number)
```

`packages/persistence/src/persistence/models/crm.py`:

```
ConsentRecord(UUIDPrimaryKey)            -> crm.consent_records
  customer_id (nullable FK), session_id (NOT NULL, indexed),
  consent_type (call_recording|data_processing|marketing, default call_recording),
  granted (bool NOT NULL), language, captured_at (server_default now())
```

Note `PaymentPlan` has **no `currency_code` column** — see D16.6.
Note `ConsentRecord` has **no `Timestamps` mixin** — order by `captured_at`, not `created_at`.

### 2.2 Write paths (do not touch — constraint 2)

`services/execution-service/src/execution_service/projections.py`

- `_PROJECTION = {EXECUTE_PAYMENT: "payment", PAYMENT_DEFERRAL: "payment_plan", ...}`
- `_payment(...)`: settles open invoices FIFO by `due_date`, then
  `session.add(Payment(..., invoice_id=settled[0].id if settled else None, method=req.payload.get("method", "card"), gateway_reference=ledger_row.adapter_reference, idempotency_key=req.idempotency_key, status="succeeded", paid_at=datetime.now(UTC)))`.
  It logs `"payment projection skipped: no billing account for %s"` and returns when the customer has no
  `billing.Account`.
- `_payment_plan(...)`: pushes invoice `due_date` forward, flips `overdue` -> `issued`, sets
  `deferral_until` to the max new due date, `status="active"`, `policy_verdict_id=to_uuid(req.policy_verdict_id)`.

**Consequence to render honestly:** `invoice_id` is `settled[0].id if settled else None`. A payment that
settled nothing carries a NULL invoice reference. The UI must show `—`, not a blank cell (§4.6).

`apps/agent-worker/src/conversation/writer.py` — writer kind `"consent"`, `record = ConsentRecord(**row)`.

### 2.3 Repository

`apps/business-api/src/business_api/repositories.py` :: `SupervisionRepository`

Existing sibling to mirror — `customer_360(customer_id)`:
- returns `None` when the customer does not exist (route turns that into 404),
- returns keys `customer_id name vip preferred_language subscriptions[] open_invoices[] tickets[]`,
- serialises invoices as `{invoice, amount, status}`.

Existing batched-lookup pattern to mirror (avoids N+1) — `ticket_list` / `session_list` build a
`customers = {...}` dict from a single `IN (...)` query.

Current imports (two lines change in §3.3):
```python
from persistence.models.billing import Invoice
from persistence.models.crm import Customer, Subscription
```

### 2.4 Routes & security

`apps/business-api/src/business_api/main.py`
- Aliases: `DbSession`, `ConseillerRole`, `SuperviseurRole`, `AdministrateurRole` (from
  `business_api.security.require_role(...)`).
- Existing: `GET /api/v1/customers/{customer_id}/360` -> `conseiller`, 404 `"customer not found"`.
- CORS: `allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(",")`,
  `allow_methods=["GET","POST","PATCH","PUT","DELETE"]`, `allow_headers=["Content-Type","X-Role"]`.

---

## 3. Endpoints

### 3.1 Reused, unchanged

| Method | Path | Role | Used for |
| --- | --- | --- | --- |
| GET | `/api/v1/customers` | conseiller | the table (untouched) |
| GET | `/api/v1/customers/{customer_id}/360` | conseiller | the modal's existing three sections (untouched) |

### 3.2 New — one endpoint

```
GET /api/v1/customers/{customer_id}/ledger      role: conseiller
```

**Role justification.** `BATCH_1_APPLY` §1 role invariant: *aggregate/cross-entity lists -> `superviseur`;
single-entity reads reached from an entity you already hold -> `conseiller`.* This is reached only from a
customer row the caller already holds, exactly like `/360`. Matching `/360` also means the modal never
splits its authorisation: a conseiller who can open the modal can read all of it.

**Response `200`:**
```json
{
  "customer_id": "3f6d…",
  "payments": [
    {
      "payment_id": "9c21…",
      "amount": 84.5,
      "currency_code": "TND",
      "method": "card",
      "status": "succeeded",
      "gateway_reference": "MOCK-PAY-A1B2C3D4E5",
      "invoice": "INV-2026-000123",
      "paid_at": "2026-07-30T09:12:44+00:00",
      "created_at": "2026-07-30T09:12:44+00:00"
    }
  ],
  "payment_plans": [
    {
      "plan_id": "4ab0…",
      "total_amount": 240.0,
      "installment_count": 3,
      "installment_amount": 80.0,
      "deferral_until": "2026-09-15",
      "status": "active",
      "policy_verdict_id": "77e1…",
      "created_at": "2026-07-12T14:03:01+00:00"
    }
  ],
  "consents": [
    {
      "consent_id": "be55…",
      "consent_type": "call_recording",
      "granted": true,
      "language": "fr",
      "session_id": "1d90…",
      "captured_at": "2026-08-01T10:22:07+00:00"
    }
  ]
}
```

**Response `404`:** `{"detail": "customer not found"}` — byte-identical to `/360`.

Empty collections return `[]`, never `null`.

### 3.3 Backend edit 1 — `apps/business-api/src/business_api/repositories.py`

**(a) Imports.** Two existing lines are extended. ruff `I001` requires alphabetical order inside each
`import` statement:

```diff
-from persistence.models.billing import Invoice
+from persistence.models.billing import Invoice, Payment, PaymentPlan
@@
-from persistence.models.crm import Customer, Subscription
+from persistence.models.crm import ConsentRecord, Customer, Subscription
```

No other import changes. `select` and `Any` are already imported for the sibling methods
(confirm with `git grep -n "from typing import" apps/business-api/src/business_api/repositories.py`; if
`Any` is somehow absent, add it — but every sibling returns `dict[str, Any]`, so it is present).

**(b) Module constant.** Place directly beneath the import block, beside any existing module-level constants:

```python
_LEDGER_LIMIT = 50
```

**(c) New method.** Append inside `class SupervisionRepository`, **immediately after `customer_360`** so the
two customer reads stay adjacent:

```python
    def customer_ledger(self, customer_id: str) -> dict[str, Any] | None:
        """Payments, deferral plans and consent captures for one customer.

        Deliberately a separate method from `customer_360`: widening that method's
        return shape would change existing behaviour for every existing caller.
        Returns None when the customer does not exist, so the route can 404 the
        same way `/360` does.
        """
        cid = to_uuid(customer_id)
        customer = self.session.execute(
            select(Customer).where(Customer.id == cid)
        ).scalar_one_or_none()
        if customer is None:
            return None

        payments = (
            self.session.execute(
                select(Payment)
                .where(Payment.customer_id == cid)
                .order_by(Payment.created_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )
        plans = (
            self.session.execute(
                select(PaymentPlan)
                .where(PaymentPlan.customer_id == cid)
                .order_by(PaymentPlan.created_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )
        consents = (
            self.session.execute(
                select(ConsentRecord)
                .where(ConsentRecord.customer_id == cid)
                .order_by(ConsentRecord.captured_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )

        # Batched invoice-number lookup, mirroring the `customers = {...}` pattern
        # used by ticket_list/session_list. Never one query per payment.
        invoice_ids = {p.invoice_id for p in payments if p.invoice_id is not None}
        invoice_numbers: dict[Any, str] = {}
        if invoice_ids:
            invoice_numbers = {
                row.id: row.invoice_number
                for row in self.session.execute(
                    select(Invoice).where(Invoice.id.in_(invoice_ids))
                ).scalars()
            }

        return {
            "customer_id": str(customer.id),
            "payments": [
                {
                    "payment_id": str(p.id),
                    "amount": float(p.amount),
                    "currency_code": p.currency_code,
                    "method": p.method,
                    "status": p.status,
                    "gateway_reference": p.gateway_reference,
                    "invoice": invoice_numbers.get(p.invoice_id),
                    "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in payments
            ],
            "payment_plans": [
                {
                    "plan_id": str(pl.id),
                    "total_amount": float(pl.total_amount),
                    "installment_count": pl.installment_count,
                    "installment_amount": float(pl.installment_amount),
                    "deferral_until": pl.deferral_until.isoformat() if pl.deferral_until else None,
                    "status": pl.status,
                    "policy_verdict_id": str(pl.policy_verdict_id) if pl.policy_verdict_id else None,
                    "created_at": pl.created_at.isoformat() if pl.created_at else None,
                }
                for pl in plans
            ],
            "consents": [
                {
                    "consent_id": str(c.id),
                    "consent_type": c.consent_type,
                    "granted": bool(c.granted),
                    "language": c.language,
                    "session_id": str(c.session_id),
                    "captured_at": c.captured_at.isoformat() if c.captured_at else None,
                }
                for c in consents
            ],
        }
```

Notes on the shape:
- `float(...)` on `Numeric` mirrors how `customer_360` already emits `open_invoices[].amount` as a JSON
  number consumed by `formatAmount`. Consistency beats Decimal purity here; these are display values.
- `national_id` is never selected. `customer_list`'s docstring rule ("deliberately does not select
  `national_id`") is honoured — the only customer field emitted is the id.
- No soft-delete filter, matching the plain lookup semantics of `customer_360`. The row is only reachable
  from `customer_list`, which is the gate for visibility.

### 3.4 Backend edit 2 — `apps/business-api/src/business_api/main.py`

Insert **immediately after** the existing `/360` handler. Copy that handler's parameter list verbatim
(same alias order, same `DbSession`/`ConseillerRole` usage) and change only the path, the repository method
and the function name:

```python
@app.get("/api/v1/customers/{customer_id}/ledger")
def customer_ledger(
    customer_id: str,
    session: DbSession,
    _: ConseillerRole,
) -> dict[str, Any]:
    data = SupervisionRepository(session).customer_ledger(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data
```

> **Apply instruction:** if the adjacent `/360` handler orders or names its parameters differently (e.g.
> constructs the repository on a separate line, or annotates the role dependency with a different
> placeholder name), match *that* file exactly rather than this block. The only requirements are: path,
> `ConseillerRole`, the `None -> 404 "customer not found"` branch.

**No ordering hazard.** FastAPI matches `/customers/{customer_id}/ledger` and `/customers/{customer_id}/360`
by distinct literal suffixes — unlike the `advisors/coverage` vs `advisors/{advisor_id}` case, no
declaration-order constraint exists. Declaring it after `/360` is style, not necessity.

### 3.5 CORS / middleware — **no change required**

| Requirement | Already satisfied by |
| --- | --- |
| Method `GET` allowed | `allow_methods=["GET","POST","PATCH","PUT","DELETE"]` |
| `X-Role` header allowed | `allow_headers=["Content-Type","X-Role"]` |
| Origin allowed | `CORS_ORIGINS` env, default `http://localhost:5174` |
| Role gate | `require_role("conseiller")` factory, unchanged |

And structurally the browser **never** reaches `:8108`: the request goes
browser -> TanStack server function -> `businessApi()` -> business-api. `X-Role` is set server-side from the
signed session cookie by `authedMiddleware`. Gate #7 ("zero direct browser requests to `:8108`") is preserved
by construction.

**No new Python dependency. No migration** — all four tables already exist (`0004_domain_writes.py`).
**No container rebuild** is required for the frontend; the business-api process must be restarted (or its
container rebuilt if the image bakes the source) to pick up the new route.

---

## 4. Frontend implementation plan

### 4.1 Files touched

| File | Change |
| --- | --- |
| `Frontend/admin_dashboard/src/lib/api/customers.server.ts` | +4 wire types, +1 server fn `getCustomerLedger` |
| `Frontend/admin_dashboard/src/lib/nexus/query-keys.ts` | +1 key `customerKeys.ledger` |
| `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts` | +3 status mappers, +2 label maps |
| `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx` | +1 query, +3 sections |

**Untouched, must show an empty diff:** `src/lib/nexus/status.ts`, `src/routes/customers.tsx`,
`package.json`, and every other route/component.

> `customers.tsx` is **not** touched. The modal is already mounted there as
> `<CustomerDetail customer={selected} onClose={...} />` and needs no new prop — the ledger is fetched from
> the `customer_id` the modal already receives.

### 4.2 `src/lib/api/customers.server.ts`

Append the types beside the existing `Customer360` block:

```ts
export type CustomerPayment = {
  payment_id: string
  amount: number
  currency_code: string
  method: string
  status: string
  gateway_reference: string | null
  invoice: string | null
  paid_at: string | null
  created_at: string | null
}

export type CustomerPaymentPlan = {
  plan_id: string
  total_amount: number
  installment_count: number
  installment_amount: number
  deferral_until: string | null
  status: string
  policy_verdict_id: string | null
  created_at: string | null
}

export type CustomerConsent = {
  consent_id: string
  consent_type: string
  granted: boolean
  language: string | null
  session_id: string
  captured_at: string | null
}

export type CustomerLedger = {
  customer_id: string
  payments: CustomerPayment[]
  payment_plans: CustomerPaymentPlan[]
  consents: CustomerConsent[]
}
```

Append the server function directly below `getCustomer360`. It is a **line-for-line clone** of
`getCustomer360` — same middleware chain, same hand-rolled validator (this file does not use zod), same
`businessApi` call shape:

```ts
export const getCustomerLedger = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: { customerId: string }) => {
    if (!data?.customerId) {
      throw new Error("customerId is required")
    }
    return { customerId: data.customerId }
  })
  .handler(async ({ data, context }) => {
    return businessApi<CustomerLedger>(
      `/api/v1/customers/${encodeURIComponent(data.customerId)}/ledger`,
      { method: "GET", role: context.session.role },
    )
  })
```

> Match `getCustomer360`'s exact validator/handler formatting in the file (argument destructuring, arrow
> style). No new import is needed — `createServerFn`, `authedMiddleware`, `requireRole` and `businessApi` are
> all already imported there.

### 4.3 `src/lib/nexus/query-keys.ts`

The file's own docstring: *"Every cookbook adds its keys here, never inline."*

```diff
 export const customerKeys = {
   all: ["customers"],
   list: (search: string, status: string, limit: number, offset: number) => [
     "customers", "list", search, status, limit, offset,
   ],
   detail: (customerId: string) => ["customers", "detail", customerId],
+  ledger: (customerId: string) => ["customers", "ledger", customerId],
 }
```

A sibling of `detail`, not a child — the two queries are independent and must invalidate independently.
Preserve the file's existing formatting/`as const` usage exactly as written there.

### 4.4 `src/lib/nexus/customer-view.ts`

Append after `invoiceStatusKey`, matching its exact declaration form (the `Record<string, StatusKey>` +
lookup-with-fallback shape used throughout this file). **The `StatusKey` type is already imported** —
add no import.

```ts
const PAYMENT_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  succeeded: "paid",
  failed: "failed",
  refunded: "refunded",
}

export function paymentStatusKey(status: string): StatusKey {
  return PAYMENT_STATUS[status] ?? "draft"
}

const PAYMENT_PLAN_STATUS: Record<string, StatusKey> = {
  proposed: "draft",
  active: "active",
  completed: "resolved",
  defaulted: "failed",
  cancelled: "closed",
}

export function paymentPlanStatusKey(status: string): StatusKey {
  return PAYMENT_PLAN_STATUS[status] ?? "draft"
}

export function consentStatusKey(granted: boolean): StatusKey {
  return granted ? "enabled" : "disabled"
}

const PAYMENT_METHOD_LABEL: Record<string, string> = {
  card: "Card",
  bank_transfer: "Bank transfer",
  wallet: "Wallet",
  voucher: "Voucher",
  cash: "Cash",
}

export function paymentMethodLabel(method: string): string {
  return PAYMENT_METHOD_LABEL[method] ?? method
}

const CONSENT_TYPE_LABEL: Record<string, string> = {
  call_recording: "Call recording",
  data_processing: "Data processing",
  marketing: "Marketing",
}

export function consentTypeLabel(type: string): string {
  return CONSENT_TYPE_LABEL[type] ?? type
}
```

**Every target key is one of the 28 canonical `status.ts` keys** — `pending paid failed refunded draft active
resolved closed enabled disabled`. `status.ts` gains **zero** lines; `StatusChip` returns `null` for unmapped
keys, so the `?? "draft"` fallbacks are what guarantee gate #12 (no blank chip) even if the backend ever
emits an unexpected enum value. The label maps mirror the existing `LANGUAGE_LABEL` + `languageLabel` pattern
in this same file.

### 4.5 `src/components/nexus/customer-detail.tsx` — imports & query

```diff
-import { getCustomer360 } from "@/lib/api/customers.server"
+import { getCustomer360, getCustomerLedger } from "@/lib/api/customers.server"
```

Extend the existing `customer-view` import with the five new helpers (keep one import statement, alphabetical
within the braces to match the file):

```ts
import {
  consentStatusKey,
  consentTypeLabel,
  formatAmount,
  invoiceStatusKey,
  languageLabel,
  paymentMethodLabel,
  paymentPlanStatusKey,
  paymentStatusKey,
  subscriptionStatusKey,
} from "@/lib/nexus/customer-view"
```

Add `formatInstant` from the audit view (already the codebase's only instant formatter — no new formatter,
D15.3 precedent) and the `Landmark` icon is **not** needed; no new icon import unless the file lacks `UserX`
(it does not).

```ts
import { formatInstant } from "@/lib/nexus/audit-view"
```

Second, **independent** query, declared directly below the existing `query`, reusing the same `enabled` flag:

```ts
  const ledgerQuery = useQuery({
    queryKey: customerKeys.ledger(customer?.customer_id ?? ""),
    queryFn: () => getCustomerLedger({ data: { customerId: customer!.customer_id } }),
    enabled,
  })
```

**Why a second query and not an extension of `getCustomer360`:** a ledger failure (new route not yet
deployed, business-api not restarted) must not blank out the Subscriptions / Invoices / Tickets sections that
work today. Independent queries give the ledger its own `CardSkeleton` and `ErrorState` and keep the existing
render path byte-identical. It also keeps the backend honest — `customer_360`'s return shape is untouched
(constraint 2).

### 4.6 `src/components/nexus/customer-detail.tsx` — the three sections

Paste as a **sibling of the existing Tickets `<section>`**, immediately after it, inside the same JSX region
that renders on 360 success. (If the file's pending / notFound / error states are early `return`s, this block
simply lives after them — the ledger then renders once 360 resolves, which is correct: there is nothing to
show a ledger *for* until the customer resolves.)

Every class string below is copied from the three existing sections of this same file — `mt-sp-7`,
`t-label text-ink-3`, `t-caption mt-sp-5 text-ink-4`, `mt-sp-5`, and the `<li>` row class.

```tsx
      {ledgerNotFound ? null : ledgerQuery.isPending ? (
        <div className="mt-sp-7">
          <CardSkeleton lines={3} />
        </div>
      ) : ledgerQuery.isError ? (
        <div className="mt-sp-7">
          <ErrorState
            error={ledgerQuery.error}
            onRetry={() => ledgerQuery.refetch()}
            title="Ledger unavailable"
          />
        </div>
      ) : (
        <>
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Payments</h3>
            {ledgerQuery.data.payments.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                No payments recorded. Payments are projected from authorised EXECUTE_PAYMENT actions.
              </p>
            ) : (
              <ul className="mt-sp-5">
                {ledgerQuery.data.payments.map((payment) => (
                  <li
                    key={payment.payment_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <StatusChip status={paymentStatusKey(payment.status)} />
                    <span className="t-body text-ink-2">{paymentMethodLabel(payment.method)}</span>
                    <span className="t-caption text-ink-4">{payment.invoice ?? "No invoice settled"}</span>
                    <span className="t-caption text-ink-4">
                      {payment.paid_at ? formatInstant(payment.paid_at) : "—"}
                    </span>
                    <span className="t-mono-l ml-auto text-ink-1">
                      {formatAmount(payment.amount, payment.currency_code)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Deferral plans</h3>
            {ledgerQuery.data.payment_plans.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                No deferral plans. Plans are projected from authorised PAYMENT_DEFERRAL actions.
              </p>
            ) : (
              <ul className="mt-sp-5">
                {ledgerQuery.data.payment_plans.map((plan) => (
                  <li
                    key={plan.plan_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <StatusChip status={paymentPlanStatusKey(plan.status)} />
                    <span className="t-body text-ink-2">
                      {plan.installment_count} × {formatAmount(plan.installment_amount)}
                    </span>
                    <span className="t-caption text-ink-4">
                      {plan.deferral_until ? `Deferred to ${plan.deferral_until}` : "No deferral date"}
                    </span>
                    <span className="t-mono-l ml-auto text-ink-1">{formatAmount(plan.total_amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Consent captures</h3>
            {ledgerQuery.data.consents.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">No consent captured for this customer.</p>
            ) : (
              <ul className="mt-sp-5">
                {ledgerQuery.data.consents.map((consent) => (
                  <li
                    key={consent.consent_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <StatusChip status={consentStatusKey(consent.granted)} />
                    <span className="t-body text-ink-2">{consentTypeLabel(consent.consent_type)}</span>
                    <span className="t-caption text-ink-4">
                      {consent.language ? languageLabel(consent.language) : "—"}
                    </span>
                    <span className="t-caption ml-auto text-ink-4">
                      {consent.captured_at ? formatInstant(consent.captured_at) : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
```

Declare the 404 guard beside the existing `notFound` constant (a ledger 404 means the customer vanished; the
existing 360 `EmptyState` already says so — showing a second error would be noise):

```ts
  const ledgerNotFound = isApiError(ledgerQuery.error) && ledgerQuery.error.status === 404
```

`isApiError` is already imported in this file for `notFound`. `StatusChip`, `CardSkeleton` and `ErrorState`
are already imported (the file renders chips for subscriptions/invoices/tickets and uses `CardSkeleton` /
`ErrorState` for the 360 states) — **verify before adding any import**; add only what `tsc` reports missing.

### 4.7 Data-flow / state matrix

| State | Rendered |
| --- | --- |
| No customer selected | Modal not rendered (`if (!customer) return null`, unchanged) |
| Ledger loading | `<CardSkeleton lines={3} />` inside `mt-sp-7` — same wrapper as the 360 skeleton |
| Ledger 404 | Nothing (the 360 `EmptyState` already owns that message) |
| Ledger error | `<ErrorState … title="Ledger unavailable" onRetry>` — 360 sections keep rendering |
| Success, all empty | Three sections, each with its honest `t-caption` explanation |
| Success, rows | Three lists; amounts right-aligned `t-mono-l ml-auto text-ink-1` |

### 4.8 Design decisions (D16.x)

| # | Decision | Reason |
| --- | --- | --- |
| **D16.1** | New endpoint, **not** a widened `/360` | Widening `customer_360()`'s return shape changes existing behaviour — constraint 2. |
| **D16.2** | Role `conseiller` | `BATCH_1_APPLY` §1 invariant; identical reach to `/360`; avoids a split-authorisation modal. |
| **D16.3** | Sections appended, **no tab bar** | No modal in this codebase has tabs. `Tabs` is a page-level primitive (G2). Adding one to a modal invents a pattern. |
| **D16.4** | Second independent `useQuery` | A ledger failure cannot degrade the working 360 render. |
| **D16.5** | `formatAmount`, not `formatCurrency` | `format.ts::formatCurrency` expects **cents**; the API emits decimal units. `customer-view.ts` documents this exact trap. |
| **D16.6** | Plan amounts use `formatAmount`'s default `"TND"` | `PaymentPlan` has no `currency_code` column. Inventing one would be a backend model change. Payments pass their real `currency_code`. |
| **D16.7** | `deferral_until` rendered as the raw `YYYY-MM-DD` string | It is a `Date` column, not an instant. `formatInstant` would fabricate a time-of-day. No new formatter (D15.3 precedent). |
| **D16.8** | `policy_verdict_id` **not** shown as a link | `/decisions` has no by-id route param; a deep link would be fabricated. It is also a loose reference, not an FK. Omitted from the row entirely to avoid a dead-end UUID; see §6.D. |
| **D16.9** | 50-row cap per collection, no pagination | Matches the modal's other sections, which are also uncapped-but-small lists. Pagination inside a 520px modal has no precedent. See §6.B. |
| **D16.10** | `invoice: null` renders "No invoice settled" | `_payment` sets `invoice_id = settled[0].id if settled else None`; a NULL is meaningful, not missing data. |
| **D16.11** | `CustomerInteraction` excluded and flagged | No writer exists anywhere; exposing it means writing business logic — constraint 3. |

---

## 5. Validation checklist

Run from `Frontend/admin_dashboard/` unless noted. Use **`git grep`** (`rg` is absent from the operator's
PATH).

### Backend
| # | Check | Expected |
| --- | --- | --- |
| 1 | `python -m ruff check apps/business-api/src/business_api/repositories.py` | All checks passed (imports alphabetised — I001) |
| 2 | `python -m ruff check apps/business-api/src/business_api/main.py` | **7 pre-existing** (I001 + 6× B904) — unchanged count |
| 3 | `python -m pytest apps/business-api/tests -q` | **25 passed** (24 baseline + the new test in §5.1) |
| 4 | `git diff --stat -- services/ infra/ packages/` | empty — no write path, no model, no migration touched |
| 5 | `git diff -- apps/business-api/src/business_api/security.py` | empty — `require_role` factory reused, not modified |
| 6 | `git grep -n "national_id" apps/business-api/src/business_api/repositories.py` | no hit inside `customer_ledger` |
| 7 | `git diff -- apps/business-api/src/business_api/main.py` shows **only** the new route + no CORS hunk | CORS/middleware untouched (additive-only, trivially satisfied) |
| 8 | `curl -H "X-Role: conseiller" .../api/v1/customers/<id>/ledger` | `200` |
| 9 | `curl -H "X-Role: conseiller" .../api/v1/customers/<random-uuid>/ledger` | `404 {"detail":"customer not found"}` |
| 10 | `curl` with no `X-Role` / an unknown role | `403` (one rank below conseiller is nothing — verify the unauth path matches `/360` exactly) |

### Frontend
| # | Check | Expected |
| --- | --- | --- |
| 11 | `node node_modules\typescript\bin\tsc --noEmit` | exit 0 |
| 12 | `npx eslint .` | 0 errors, **exactly 9** warnings (7× `react-refresh/only-export-components`, 2× `react-hooks/exhaustive-deps`) |
| 13 | `npm run build` (client + SSR + nitro) | exit 0 |
| 14 | `npx prettier --write` on **touched files only** — never `bun run format` | exit 0 |
| 15 | `git diff -- src/lib/nexus/status.ts` | empty |
| 16 | `git diff --stat -- package.json` | empty — no new dependency |
| 17 | `git diff --stat -- src/routes/` | empty — `customers.tsx` not touched |
| 18 | `git grep -nE "rgb\(\|#[0-9a-fA-F]{3,6}" src/components/nexus/customer-detail.tsx src/lib/nexus/customer-view.ts` | no hits |
| 19 | `git grep -nE "toLocaleString\(\|new Date\(\|getDay\(\|getHours\(" src/components/nexus/customer-detail.tsx` | no hits (dates go through `formatInstant`) |
| 20 | Every class string in the new JSX also appears elsewhere in `customer-detail.tsx` | true — sections are copies of the existing three |
| 21 | Every `StatusChip` renders non-blank for every backend enum value (4 payment + 5 plan + 2 consent) | true — all map into the 28 canonical keys, with `?? "draft"` fallbacks |
| 22 | Overlay portal | inherited unmodified from `modal.tsx`; no overlay code added |
| 23 | Zero direct browser requests to `:8108` (DevTools Network) | true — server function only |

### 5.1 New test — `apps/business-api/tests/test_customer_ledger.py`

`conftest.py` provides a DB-backed `db_session` fixture (live engine, rolled-back transaction, leaves no
trace). This test needs **no seeded data** and is therefore deterministic:

```python
"""Contract test for the additive customer ledger read."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from business_api.repositories import SupervisionRepository


def test_customer_ledger_unknown_customer_returns_none(db_session: Session) -> None:
    """Mirrors customer_360: a missing customer yields None so the route can 404."""
    repo = SupervisionRepository(db_session)
    assert repo.customer_ledger(str(uuid4())) is None


def test_customer_ledger_shape_is_stable(db_session: Session) -> None:
    """Every collection is a list, never None, for a customer that exists."""
    from persistence.models.crm import Customer

    customer = Customer(first_name="Ledger", last_name="Probe", status="active")
    db_session.add(customer)
    db_session.flush()

    data = SupervisionRepository(db_session).customer_ledger(str(customer.id))
    assert data is not None
    assert data["customer_id"] == str(customer.id)
    assert data["payments"] == []
    assert data["payment_plans"] == []
    assert data["consents"] == []
```

> **Baseline moves 24 -> 26.** State this in the patch report so the change is not mistaken for drift.
> If `Customer` has NOT NULL columns beyond those three (check the model before running — `national_id`
> is unique but may be nullable), add the minimum required kwargs; do **not** set `national_id`.
> If that second test proves brittle for schema reasons, drop it and ship only the first — baseline 24 -> 25.

---

## 6. Ambiguities requiring your confirmation before implementation

**A. `crm.CustomerInteraction` — dead table.** Confirmed by `search_code`: zero writers in the live tree.
My call is to leave it unexposed and flag it (constraint 3: this is missing *logic*, not missing *access*).
The alternative is a separate cookbook that adds an interaction-write hook to the agent worker's conversation
writer — a genuine new feature needing your go/no-go. **Confirm: leave flagged?**

**B. 50-row cap, no pagination.** A customer with hundreds of payments would silently show only the newest
50. Options: (i) keep the cap silently, (ii) keep the cap and add a `t-caption` "Showing latest 50" when the
collection is full, (iii) paginate. My recommendation is **(ii)** — honest, one line, no new pattern.
**Which?**

**C. The "Total invoiced" mislabel (pre-existing, not introduced here).** `customer_360()` calls its list
`open_invoices` but filters only `i.status != "paid"`, and `customer-detail.tsx` labels the sum
**"Total invoiced"**. Live data has no `paid` invoices at all, so the two labels currently disagree with each
other and with the filter. This is adjacent to FEATURE_16 but is a **correction**, not access work. Fix it
here in the same patch (one label string), or as its own small cookbook? **Your call.**

**D. `policy_verdict_id`.** D16.8 omits it. If you want the plan traceable to its authorising verdict, the
honest route is a new `/decisions?verdict=<id>` search param + a filtered fetch — that is new frontend
behaviour and belongs in its own cookbook. Options: (i) omit as specified, (ii) render it as inert
`t-mono-s` text, (iii) new cookbook for the deep link. **Which?**

**E. Business-api restart.** Unlike FEATURE_15, this patch adds a backend route, so the running business-api
must be restarted (or its image rebuilt if the source is baked in rather than bind-mounted). Confirm your
local setup so I can word the apply steps correctly.

---

## 7. Files touched — summary

| File | Type | Change |
| --- | --- | --- |
| `apps/business-api/src/business_api/repositories.py` | modified | +2 import symbols, +1 constant, +1 method (`customer_ledger`) |
| `apps/business-api/src/business_api/main.py` | modified | +1 GET route (no CORS/middleware change) |
| `apps/business-api/tests/test_customer_ledger.py` | **new** | 2 contract tests |
| `Frontend/admin_dashboard/src/lib/api/customers.server.ts` | modified | +4 types, +1 server fn |
| `Frontend/admin_dashboard/src/lib/nexus/query-keys.ts` | modified | +1 key |
| `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts` | modified | +3 mappers, +2 label maps |
| `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx` | modified | +imports, +1 query, +1 guard, +3 sections |

**Never touched:** `src/lib/nexus/status.ts` · `src/routes/*` · `package.json` · `services/` · `packages/` ·
`infra/` · any migration · any write path · `Frontend/customer_portal` · `apps/client-widget`.
