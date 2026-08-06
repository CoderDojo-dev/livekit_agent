# FEATURE_17 — Service actions: live balances, plan history & action projections

> Branch of truth: `version_81` @ `2f10a07` (GitHub). Operator local HEAD: `f584eef` + FEATURE_15 + FEATURE_16 (unpushed).
> Scope: **admin dashboard only**. Backend change is **additive-only** (one new repository method + one new GET route).
> Design system: **locked**. Every class string below is copied from `customer-detail.tsx`'s existing sections.
> Backend route added -> **the business-api image must be rebuilt**, not restarted (established by FEATURE_16 §6.E).

---

## 1. Feature name & scope

**Service actions** — the last unexposed slice of `projections.py`. FEATURE_16 surfaced the *money*
projections (payments, deferral plans) and consent. This one surfaces the *service* projections and the live
line state they move:

| Surfaced | Table | Written by |
| --- | --- | --- |
| Live prepaid balances | `ocs.balance_accounts` | `projections.py::_main_balance` + `_recharge` (also seeded) |
| Plan history | `provisioning.plan_change_history` | `projections.py::_provisioning` (CHANGE_PLAN branch) |
| Top-ups | `ocs.recharges` | `projections.py::_recharge` |
| SIM cases | `sim.block_unblock_cases` | `projections.py::_sim_case` |
| SIM orders | `provisioning.sim_orders` | `projections.py::_sim_order` |
| Provisioning requests | `provisioning.provisioning_requests` | `projections.py::_provisioning` |

**Placement:** three new read-only `<section>` blocks appended to the customer 360 modal
(`components/nexus/customer-detail.tsx`), below the FEATURE_16 *Consent captures* section. One new endpoint.

### 1.1 Why this is not a duplicate of `/decisions`

I checked before proposing a second surface for the same data. `GET /api/v1/actions` exists
(`status: str = "failed"`, superviseur) but **no frontend file calls it** — `search_code "api/v1/actions"`
returns only `main.py` and two stale `patches/` copies. What the frontend *does* have is `/decisions`, whose
`listDecisions` embeds a `DecisionAction[]` per decision — i.e. `execution.action_ledger` rows: the **request
and its dispatch attempt** (`action_type`, `status`, `attempt_count`, `error_message`, `reference`).

What `/decisions` cannot show is the **durable effect**. `projections.py`'s own docstring states the
distinction exactly:

> *"Without (2) an action is only a receipt: the caller pays their bill, a payments row appears, and the very
> next question still answers 'you owe 42.500 TND' because billing.invoices never moved."*

`/decisions` is the receipt. This feature is the effect: the balance that actually moved, the plan the line
actually sits on, the SIM order actually raised. Different table, different question, different audience
(customer-scoped, not supervision-scoped). **Not a duplicate.**

### 1.2 Why three sections and not one timeline

The six tables are **not one kind of thing**, and merging them would force a fabricated status:

- `ocs.balance_accounts` is **current state**, not an event. It has no event time — only `updated_at`.
- `provisioning.plan_change_history` is a **state transition** with **no `status` column at all**. Putting it
  in an event list with a `StatusChip` would require inventing a status for it.
- The other four each carry a genuine lifecycle enum and a genuine timestamp — they merge cleanly.

So: **Live balances** (state) · **Plan history** (transitions, no chip) · **Service actions** (4-source merged
event list, real chips). Every row's chip is backed by a real column. See D17.3.

### 1.3 The `_provisioning` double-write (read this before reviewing the UI)

`_provisioning` writes **two rows** for a `CHANGE_PLAN`: a `ProvisioningRequest` *and* a `PlanChangeHistory`.
They share no foreign key — only a subscription and a near-identical timestamp. Joining them by timestamp
proximity would be fabrication, so I do not. Consequence: **one plan change legitimately appears twice** — once
in *Service actions* as "Plan change", once in *Plan history* as `from → to`. This is the data, not a bug.
The section headings make the two readings distinct (what was requested vs. what the line now runs).
See §6.C if you would rather suppress one.

### 1.4 Honest data-state disclosure

`execution.action_ledger` holds **0 rows** locally, and all four event tables are written **only** by
projections of AUTHORIZED executions — so *Service actions* and *Plan history* will almost certainly render
**empty** today, exactly as FEATURE_16's payments did.

**`ocs.balance_accounts` is the exception.** It is live state the Context façade reads back *during* calls
(`crm.v_subscription_live` re-presents it), and `_main_balance` only *opens* a row when one is missing — the
seed data is expected to already carry balances. **This is the one section likely to show real rows on the
first load.** That makes it the honest end-to-end proof for this patch.

---

## 2. Backend reference (existing, verified at `2f10a07`)

### 2.1 Models

`packages/persistence/src/persistence/models/ocs.py`
```
BalanceAccount(UUIDPrimaryKey)          -> ocs.balance_accounts
  subscription_id (FK, NOT NULL, indexed), customer_id (FK, NOT NULL),
  balance_type   CHECK IN ('main','data','voice','sms'),
  balance_value  Numeric(14,4) default 0,
  balance_unit   CHECK IN ('TND','GB','MB','MIN','SMS'),
  expiry_date (Date, nullable), status CHECK IN ('active','expired','suspended'),
  updated_at (server_default now())
  UNIQUE (subscription_id, balance_type)

Recharge(UUIDPrimaryKey)                -> ocs.recharges
  subscription_id (FK, NOT NULL), customer_id (FK, NOT NULL),
  recharge_code (nullable), amount Numeric(12,2), bonus_amount Numeric(12,2) default 0,
  channel CHECK IN ('app','web','ussd','scratch_card','agent'),
  idempotency_key (unique), transaction_reference, 
  status CHECK IN ('pending','completed','failed'), created_at
```

`packages/persistence/src/persistence/models/sim.py`
```
BlockUnblockCase(UUIDPrimaryKey, Timestamps) -> sim.block_unblock_cases
  subscription_id (FK, NOT NULL, indexed)   <-- NO customer_id column
  action CHECK IN ('BLOCK','UNBLOCK','UNLOCK_PUK','REACTIVATE'),
  status CHECK IN ('pending','identity_verified','completed','escalated','rejected'),
  identity_verified (bool), policy_verdict_id (loose ref), idempotency_key (unique)
```

`packages/persistence/src/persistence/models/provisioning.py`
```
ProvisioningRequest(UUIDPrimaryKey, Timestamps) -> provisioning.provisioning_requests
  subscription_id (nullable FK, indexed), customer_id (nullable FK),
  action_type (String 60), status CHECK IN ('pending','in_progress','completed','failed'),
  idempotency_key (unique), policy_verdict_id, parameters (JSONB),
  requested_at (server_default now()), completed_at (nullable)

SimOrder(UUIDPrimaryKey, Timestamps)            -> provisioning.sim_orders
  customer_id (nullable FK, indexed), subscription_id (nullable FK),
  sim_type CHECK IN ('physical','esim'), iccid (nullable),
  status CHECK IN ('requested','shipped','activated','cancelled'), tracking_code

PlanChangeHistory(UUIDPrimaryKey)               -> provisioning.plan_change_history
  subscription_id (nullable FK, indexed)    <-- NO customer_id column, NO status column
  from_plan (nullable), to_plan (NOT NULL),
  changed_by CHECK IN ('agent','self_service','advisor'),
  effective_date (Date, nullable), created_at
```

> **Query-shaping finding.** `BlockUnblockCase` and `PlanChangeHistory` have **no `customer_id` column**.
> They can only be reached through the customer's subscriptions. `SimOrder.customer_id` and
> `ProvisioningRequest.customer_id` are **nullable**, so a customer-id-only filter would silently drop rows
> attached to the line but not the customer. The repository therefore resolves subscription ids first and
> filters those two tables with `or_(customer_id == cid, subscription_id.in_(sub_ids))`. See D17.2.

### 2.2 Write paths (do not touch — constraint 2)

All in `services/execution-service/src/execution_service/projections.py`:

- `_recharge`: `Recharge(..., channel="agent", transaction_reference=ledger_row.adapter_reference, status="completed")`, then credits `BalanceAccount.balance_value` (main/TND) and stamps `updated_at`.
- `_sim_case`: `BlockUnblockCase(..., status="completed", identity_verified=True, ...)`, then forces `Subscription.status = "ACTIVE"`.
- `_sim_order`: `SimOrder(..., sim_type=payload or "physical", status="requested", tracking_code=ledger_row.adapter_reference)`.
- `_provisioning`: `ProvisioningRequest(..., status="completed", parameters=req.payload, completed_at=now)`; for CHANGE_PLAN also `PlanChangeHistory(from_plan=subscription.plan_code, to_plan=..., changed_by="agent", effective_date=date.today())` and mutates `subscription.plan_code`; for ACTIVATE_ROAMING sets `subscription.roaming_enabled = True`.

### 2.3 What the hardcoded projection literals mean for the UI

This matters for honest chips, so it is stated up front rather than discovered at review:

| Column | Enum allows | Projection ever writes | Consequence |
| --- | --- | --- | --- |
| `Recharge.channel` | 5 values | **only `"agent"`** | The channel label will always read "Agent". |
| `Recharge.status` | 3 values | **only `"completed"`** | Chip near-constant. |
| `BlockUnblockCase.status` | 5 values | **only `"completed"`** | Chip near-constant. |
| `BlockUnblockCase.identity_verified` | bool | **only `True`** | Not rendered — a constant true is not evidence. |
| `BlockUnblockCase.action` | 4 values | only `UNBLOCK`, `REACTIVATE` (`_SIM_ACTION`) | `BLOCK` / `UNLOCK_PUK` never appear; still mapped. |
| `SimOrder.status` | 4 values | **only `"requested"`** | **No fulfilment write path exists** — orders never reach shipped/activated. See §6.B. |
| `SimOrder.iccid` | — | **never set** | Omitted from the payload; always NULL. |
| `ProvisioningRequest.status` | 4 values | **only `"completed"`** | Chip near-constant. |
| `PlanChangeHistory.changed_by` | 3 values | **only `"agent"`** | Label rendered anyway (seed data may differ). |

All enum values are still mapped in §4.4 — a chip must never blank out if seed data or a future writer
supplies a value the projection does not.

### 2.4 Deliberate omissions from the payload

| Field | Why it is not returned |
| --- | --- |
| `ProvisioningRequest.parameters` (JSONB) | It is the raw action payload. `/decisions` already exposes action `parameters` — but to **superviseur**. This route is **conseiller**. Returning the same payload one rank lower would be a privilege inversion. Omitted. |
| `policy_verdict_id` (on `BlockUnblockCase`, `ProvisioningRequest`) | D16.8 precedent — no `/decisions?verdict=` param exists, so any link would be fabricated and a bare UUID is a dead end. |
| `idempotency_key` (all four) | Internal execution-contract key, not operator-facing. |
| `Recharge.recharge_code` | A voucher code (never written by the projection). Not exposed. |
| `SimOrder.iccid` | SIM serial; never written. Not exposed. |

---

## 3. Endpoints

### 3.1 Reused, unchanged

| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/v1/customers/{customer_id}/360` | conseiller |
| GET | `/api/v1/customers/{customer_id}/ledger` | conseiller (FEATURE_16) |

### 3.2 New — one endpoint

```
GET /api/v1/customers/{customer_id}/service-actions      role: conseiller
```

Role matches `/360` and `/ledger`: a single-entity read reached from a customer the caller already holds
(`BATCH_1_APPLY` §1). Keeping all three modal reads at one rank means the modal never half-renders on a
permission boundary.

**Response `200`:**
```json
{
  "customer_id": "2187de39…",
  "balances": [
    {
      "balance_id": "a1…", "subscription_id": "b2…", "msisdn": "21620123456",
      "balance_type": "main", "balance_value": 42.5, "balance_unit": "TND",
      "status": "active", "expiry_date": "2026-12-31", "updated_at": "2026-08-01T10:22:07+00:00"
    }
  ],
  "plan_changes": [
    {
      "change_id": "c3…", "subscription_id": "b2…", "msisdn": "21620123456",
      "from_plan": "PREPAID_S", "to_plan": "PREPAID_L", "changed_by": "agent",
      "effective_date": "2026-08-01", "created_at": "2026-08-01T10:22:07+00:00"
    }
  ],
  "events": [
    { "event_id": "d4…", "source": "recharge", "status": "completed",
      "occurred_at": "2026-08-01T10:22:07+00:00", "subscription_id": "b2…",
      "msisdn": "21620123456", "reference": "MOCK-TOP-A1B2C3D4E5",
      "amount": 20.0, "bonus_amount": 0.0, "channel": "agent" },
    { "event_id": "e5…", "source": "sim_case", "status": "completed",
      "occurred_at": "…", "subscription_id": "b2…", "msisdn": "…",
      "reference": null, "action": "UNBLOCK" },
    { "event_id": "f6…", "source": "sim_order", "status": "requested",
      "occurred_at": "…", "subscription_id": "b2…", "msisdn": "…",
      "reference": "MOCK-SIM-…", "sim_type": "physical" },
    { "event_id": "a7…", "source": "provisioning", "status": "completed",
      "occurred_at": "…", "completed_at": "…", "subscription_id": "b2…",
      "msisdn": "…", "reference": null, "action_type": "CHANGE_PLAN" }
  ]
}
```

**Response `404`:** `{"detail": "customer not found"}` — byte-identical to `/360` and `/ledger`.
Empty collections return `[]`, never `null`.

### 3.3 Backend edit 1 — `apps/business-api/src/business_api/repositories.py`

**(a) Imports.** Three **new lines**, inserted so the `persistence.models.*` block stays alphabetical
(`billing, conversation, crm, execution, ocs, policy, provisioning, reference, sim, ticketing`) — ruff `I001`:

```diff
 from persistence.models.execution import ActionLedger
+from persistence.models.ocs import BalanceAccount, Recharge
 from persistence.models.policy import PolicyVerdict
+from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder
 from persistence.models.reference import BusinessRule, ErrorCatalog, GeoArea, Product, RechargeCatalog
+from persistence.models.sim import BlockUnblockCase
 from persistence.models.ticketing import Ticket
```

`or_` and `select` are already imported (`or_` is used by `customer_list`'s ilike search). Verify with
`git grep -n "^from sqlalchemy import" apps/business-api/src/business_api/repositories.py` and add nothing else.

**(b) Module constant.** Beside `_LEDGER_LIMIT` (added by FEATURE_16):

```python
_SERVICE_LIMIT = 50
```

**(c) New method.** Append inside `class SupervisionRepository`, **immediately after `customer_ledger()`**,
keeping the three customer reads adjacent:

```python
    def customer_service_actions(self, customer_id: str) -> dict[str, Any] | None:
        """Live balances, plan history and service-action projections for one customer.

        Separate from customer_360/customer_ledger for the same reason as FEATURE_16:
        widening an existing method's return shape changes existing behaviour.

        Two of these tables (sim.block_unblock_cases, provisioning.plan_change_history)
        carry no customer_id, and two more allow it to be NULL, so everything is scoped
        through the customer's live subscriptions.
        """
        cid = to_uuid(customer_id)
        customer = self.session.execute(
            select(Customer).where(Customer.id == cid)
        ).scalar_one_or_none()
        if customer is None:
            return None

        subscriptions = list(
            self.session.execute(
                select(Subscription).where(
                    Subscription.customer_id == cid,
                    Subscription.deleted_at.is_(None),
                )
            ).scalars()
        )
        sub_ids = [s.id for s in subscriptions]
        msisdn_by_sub = {s.id: s.msisdn for s in subscriptions}

        # Tables with a nullable/absent customer_id must also be reachable by line.
        recharge_scope = Recharge.customer_id == cid
        sim_order_scope = SimOrder.customer_id == cid
        provisioning_scope = ProvisioningRequest.customer_id == cid
        if sub_ids:
            recharge_scope = or_(recharge_scope, Recharge.subscription_id.in_(sub_ids))
            sim_order_scope = or_(sim_order_scope, SimOrder.subscription_id.in_(sub_ids))
            provisioning_scope = or_(
                provisioning_scope, ProvisioningRequest.subscription_id.in_(sub_ids)
            )

        balances: list[BalanceAccount] = []
        plan_changes: list[PlanChangeHistory] = []
        sim_cases: list[BlockUnblockCase] = []
        if sub_ids:
            balances = list(
                self.session.execute(
                    select(BalanceAccount)
                    .where(BalanceAccount.subscription_id.in_(sub_ids))
                    .order_by(BalanceAccount.balance_type.asc())
                ).scalars()
            )
            plan_changes = list(
                self.session.execute(
                    select(PlanChangeHistory)
                    .where(PlanChangeHistory.subscription_id.in_(sub_ids))
                    .order_by(PlanChangeHistory.created_at.desc())
                    .limit(_SERVICE_LIMIT)
                ).scalars()
            )
            sim_cases = list(
                self.session.execute(
                    select(BlockUnblockCase)
                    .where(BlockUnblockCase.subscription_id.in_(sub_ids))
                    .order_by(BlockUnblockCase.created_at.desc())
                    .limit(_SERVICE_LIMIT)
                ).scalars()
            )

        recharges = list(
            self.session.execute(
                select(Recharge)
                .where(recharge_scope)
                .order_by(Recharge.created_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )
        sim_orders = list(
            self.session.execute(
                select(SimOrder)
                .where(sim_order_scope)
                .order_by(SimOrder.created_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )
        provisioning_rows = list(
            self.session.execute(
                select(ProvisioningRequest)
                .where(provisioning_scope)
                .order_by(ProvisioningRequest.requested_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )

        events: list[dict[str, Any]] = []
        for row in recharges:
            events.append({
                "event_id": str(row.id),
                "source": "recharge",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id),
                "msisdn": msisdn_by_sub.get(row.subscription_id),
                "reference": row.transaction_reference,
                "amount": float(row.amount),
                "bonus_amount": float(row.bonus_amount),
                "channel": row.channel,
            })
        for row in sim_cases:
            events.append({
                "event_id": str(row.id),
                "source": "sim_case",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id),
                "msisdn": msisdn_by_sub.get(row.subscription_id),
                "reference": None,
                "action": row.action,
            })
        for row in sim_orders:
            events.append({
                "event_id": str(row.id),
                "source": "sim_order",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id) if row.subscription_id else None,
                "msisdn": msisdn_by_sub.get(row.subscription_id) if row.subscription_id else None,
                "reference": row.tracking_code,
                "sim_type": row.sim_type,
            })
        for row in provisioning_rows:
            events.append({
                "event_id": str(row.id),
                "source": "provisioning",
                "status": row.status,
                "occurred_at": row.requested_at.isoformat() if row.requested_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "subscription_id": str(row.subscription_id) if row.subscription_id else None,
                "msisdn": msisdn_by_sub.get(row.subscription_id) if row.subscription_id else None,
                "reference": None,
                "action_type": row.action_type,
            })

        # All four timestamps are tz-aware UTC isoformat strings, so lexicographic
        # ordering is chronological. Rows with no timestamp sort last.
        events.sort(key=lambda event: event["occurred_at"] or "", reverse=True)

        return {
            "customer_id": str(customer.id),
            "balances": [
                {
                    "balance_id": str(b.id),
                    "subscription_id": str(b.subscription_id),
                    "msisdn": msisdn_by_sub.get(b.subscription_id),
                    "balance_type": b.balance_type,
                    "balance_value": float(b.balance_value),
                    "balance_unit": b.balance_unit,
                    "status": b.status,
                    "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                    "updated_at": b.updated_at.isoformat() if b.updated_at else None,
                }
                for b in balances
            ],
            "plan_changes": [
                {
                    "change_id": str(c.id),
                    "subscription_id": str(c.subscription_id) if c.subscription_id else None,
                    "msisdn": msisdn_by_sub.get(c.subscription_id) if c.subscription_id else None,
                    "from_plan": c.from_plan,
                    "to_plan": c.to_plan,
                    "changed_by": c.changed_by,
                    "effective_date": c.effective_date.isoformat() if c.effective_date else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in plan_changes
            ],
            "events": events[:_SERVICE_LIMIT],
        }
```

Notes:
- `national_id` is never selected — the only customer field emitted is the id.
- `float(...)` on `Numeric` matches the `customer_360` / `customer_ledger` precedent. `balance_value` is
  `Numeric(14,4)`; see D17.6 for the display rounding.
- The `if row.subscription_id else None` guards on the nullable columns keep the dict key type honest and
  keep mypy quiet.

### 3.4 Backend edit 2 — `apps/business-api/src/business_api/main.py`

Insert **immediately after** the FEATURE_16 `/ledger` handler, copying that handler's parameter list verbatim:

```python
@app.get("/api/v1/customers/{customer_id}/service-actions")
def customer_service_actions(
    customer_id: str,
    session: DbSession,
    _: ConseillerRole,
) -> dict[str, Any]:
    data = SupervisionRepository(session).customer_service_actions(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data
```

> Match the `/ledger` handler exactly as it now stands in your tree (that is the one you just wrote and
> verified). No ordering hazard: `/360`, `/ledger` and `/service-actions` are three distinct literal suffixes.

### 3.5 CORS / middleware — **no change required**

Identical to FEATURE_16 §3.5: `GET` is in `allow_methods`, `X-Role` is in `allow_headers`, the origin comes
from `CORS_ORIGINS`, and the browser never reaches `:8108` (server function -> `businessApi()` only).
`require_role` is reused as a factory, not modified.

**No new Python dependency. No migration** — all six tables exist (`0004_domain_writes.py`).
**Rebuild the business-api image** (`apps/business-api/Dockerfile` bakes the source — FEATURE_16 §6.E).

---

## 4. Frontend implementation plan

### 4.1 Files touched

| File | Change |
| --- | --- |
| `src/lib/api/customers.server.ts` | +7 wire types, +1 server fn `getCustomerServiceActions` |
| `src/lib/nexus/query-keys.ts` | +1 key `customerKeys.serviceActions` |
| `src/lib/nexus/customer-view.ts` | +4 status maps, +1 event status fn, +5 label helpers |
| `src/components/nexus/customer-detail.tsx` | +1 query, +1 404 guard, +3 sections |

**Untouched:** `status.ts`, `src/routes/*`, `package.json`, everything else.

### 4.2 `src/lib/api/customers.server.ts`

Append beside the FEATURE_16 ledger types:

```ts
export type CustomerBalance = {
  balance_id: string
  subscription_id: string
  msisdn: string | null
  balance_type: string
  balance_value: number
  balance_unit: string
  status: string
  expiry_date: string | null
  updated_at: string | null
}

export type CustomerPlanChange = {
  change_id: string
  subscription_id: string | null
  msisdn: string | null
  from_plan: string | null
  to_plan: string
  changed_by: string
  effective_date: string | null
  created_at: string | null
}

type ServiceEventBase = {
  event_id: string
  status: string
  occurred_at: string | null
  subscription_id: string | null
  msisdn: string | null
  reference: string | null
}

export type RechargeEvent = ServiceEventBase & {
  source: "recharge"
  amount: number
  bonus_amount: number
  channel: string
}

export type SimCaseEvent = ServiceEventBase & {
  source: "sim_case"
  action: string
}

export type SimOrderEvent = ServiceEventBase & {
  source: "sim_order"
  sim_type: string
}

export type ProvisioningEvent = ServiceEventBase & {
  source: "provisioning"
  action_type: string
  completed_at: string | null
}

/** Discriminated on `source` — the repository normalises four tables into one ordered list. */
export type ServiceEvent =
  | RechargeEvent
  | SimCaseEvent
  | SimOrderEvent
  | ProvisioningEvent

export type CustomerServiceActions = {
  customer_id: string
  balances: CustomerBalance[]
  plan_changes: CustomerPlanChange[]
  events: ServiceEvent[]
}
```

Server function — a clone of `getCustomerLedger`. **Copy that function's exact validator shape from your
tree** (you applied it with a `raw: unknown` validator rather than the inline-typed form in the FEATURE_16
cookbook; match what is actually there, not what that cookbook printed):

```ts
export const getCustomerServiceActions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((raw: unknown) => {
    const data = raw as { customerId?: string }
    if (!data?.customerId) {
      throw new Error("customerId is required")
    }
    return { customerId: data.customerId }
  })
  .handler(async ({ data, context }) => {
    return businessApi<CustomerServiceActions>(
      `/api/v1/customers/${encodeURIComponent(data.customerId)}/service-actions`,
      { method: "GET", role: context.session.role },
    )
  })
```

No new imports.

### 4.3 `src/lib/nexus/query-keys.ts`

```diff
   detail: (customerId: string) => ["customers", "detail", customerId],
   ledger: (customerId: string) => ["customers", "ledger", customerId],
+  serviceActions: (customerId: string) => ["customers", "serviceActions", customerId],
 }
```

### 4.4 `src/lib/nexus/customer-view.ts`

Append after the FEATURE_16 helpers. Add one type import at the top of the file — this mirrors
`decision-view.ts`, which already does `import type { Decision, Verdict } from "@/lib/api/decisions.server"`:

```ts
import type { ServiceEvent } from "@/lib/api/customers.server"
```

```ts
const BALANCE_STATUS: Record<string, StatusKey> = {
  active: "active",
  expired: "inactive",
  suspended: "suspended",
}

export function balanceStatusKey(status: string): StatusKey {
  return BALANCE_STATUS[status] ?? "inactive"
}

const RECHARGE_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  completed: "resolved",
  failed: "failed",
}

const SIM_CASE_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  identity_verified: "in_progress",
  completed: "resolved",
  escalated: "escalated",
  rejected: "closed",
}

const SIM_ORDER_STATUS: Record<string, StatusKey> = {
  requested: "pending",
  shipped: "in_progress",
  activated: "active",
  cancelled: "closed",
}

const PROVISIONING_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  in_progress: "in_progress",
  completed: "resolved",
  failed: "failed",
}

/**
 * Each source has its own lifecycle vocabulary; there is no shared enum.
 * Falls back to "open" so a StatusChip never renders blank — the precedent set by
 * decision-view.ts::actionStatusKey.
 */
export function serviceEventStatusKey(event: ServiceEvent): StatusKey {
  switch (event.source) {
    case "recharge":
      return RECHARGE_STATUS[event.status] ?? "open"
    case "sim_case":
      return SIM_CASE_STATUS[event.status] ?? "open"
    case "sim_order":
      return SIM_ORDER_STATUS[event.status] ?? "open"
    case "provisioning":
      return PROVISIONING_STATUS[event.status] ?? "open"
    default:
      return "open"
  }
}

const BALANCE_TYPE_LABEL: Record<string, string> = {
  main: "Main credit",
  data: "Data",
  voice: "Voice",
  sms: "SMS",
}

export function balanceTypeLabel(type: string): string {
  return BALANCE_TYPE_LABEL[type] ?? type
}

const SIM_ACTION_LABEL: Record<string, string> = {
  BLOCK: "SIM block",
  UNBLOCK: "SIM unblock",
  UNLOCK_PUK: "PUK unlock",
  REACTIVATE: "SIM reactivation",
}

const PROVISIONING_ACTION_LABEL: Record<string, string> = {
  CHANGE_PLAN: "Plan change",
  ACTIVATE_ROAMING: "Roaming activation",
}

const SIM_TYPE_LABEL: Record<string, string> = {
  physical: "Physical SIM",
  esim: "eSIM",
}

/** One-line title per event; never blank, always derived from a real column. */
export function serviceEventTitle(event: ServiceEvent): string {
  switch (event.source) {
    case "recharge":
      return "Top-up"
    case "sim_case":
      return SIM_ACTION_LABEL[event.action] ?? event.action
    case "sim_order":
      return `SIM order · ${SIM_TYPE_LABEL[event.sim_type] ?? event.sim_type}`
    case "provisioning":
      return PROVISIONING_ACTION_LABEL[event.action_type] ?? event.action_type
    default:
      return "Service action"
  }
}

const CHANGED_BY_LABEL: Record<string, string> = {
  agent: "Agent",
  self_service: "Self-service",
  advisor: "Advisor",
}

export function changedByLabel(changedBy: string): string {
  return CHANGED_BY_LABEL[changedBy] ?? changedBy
}

const RECHARGE_CHANNEL_LABEL: Record<string, string> = {
  app: "App",
  web: "Web",
  ussd: "USSD",
  scratch_card: "Scratch card",
  agent: "Agent",
}

export function rechargeChannelLabel(channel: string): string {
  return RECHARGE_CHANNEL_LABEL[channel] ?? channel
}
```

**Every target key is one of the 28 canonical `status.ts` keys** — `active inactive suspended pending
in_progress resolved escalated closed failed open`. `status.ts` gains zero lines.

### 4.5 `src/components/nexus/customer-detail.tsx` — imports, query, guard

Extend the two existing import statements (do not add new ones):

```diff
-import { getCustomer360, getCustomerLedger } from "@/lib/api/customers.server"
+import {
+  getCustomer360,
+  getCustomerLedger,
+  getCustomerServiceActions,
+} from "@/lib/api/customers.server"
```

Add to the existing `@/lib/nexus/customer-view` import, alphabetically:
`balanceStatusKey`, `balanceTypeLabel`, `changedByLabel`, `rechargeChannelLabel`, `serviceEventStatusKey`,
`serviceEventTitle`.

Third independent query, below `ledgerQuery`, reusing the same `enabled`:

```ts
  const serviceQuery = useQuery({
    queryKey: customerKeys.serviceActions(customer?.customer_id ?? ""),
    queryFn: () =>
      getCustomerServiceActions({ data: { customerId: customer!.customer_id } }),
    enabled,
  })

  const serviceNotFound =
    isApiError(serviceQuery.error) && serviceQuery.error.status === 404
```

Same reasoning as D16.4: an independent query means a service-actions failure cannot blank the 360 sections
or the ledger sections, and vice versa.

### 4.6 `src/components/nexus/customer-detail.tsx` — the three sections

Paste **immediately after the FEATURE_16 "Consent captures" `</section>`**, as its sibling. Every class
string is copied from the existing sections in this file.

```tsx
      {serviceNotFound ? null : serviceQuery.isPending ? (
        <div className="mt-sp-7">
          <CardSkeleton lines={3} />
        </div>
      ) : serviceQuery.isError ? (
        <div className="mt-sp-7">
          <ErrorState
            error={serviceQuery.error}
            onRetry={() => serviceQuery.refetch()}
            title="Service actions unavailable"
          />
        </div>
      ) : (
        <>
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Live balances</h3>
            {serviceQuery.data.balances.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                No balance accounts on this customer's lines.
              </p>
            ) : (
              <ul className="mt-sp-5">
                {serviceQuery.data.balances.map((balance) => (
                  <li
                    key={balance.balance_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <StatusChip status={balanceStatusKey(balance.status)} />
                    <span className="t-body text-ink-2">
                      {balanceTypeLabel(balance.balance_type)}
                    </span>
                    <span className="t-caption text-ink-4">{balance.msisdn ?? "—"}</span>
                    <span className="t-caption text-ink-4">
                      {balance.expiry_date ? `Expires ${balance.expiry_date}` : "No expiry"}
                    </span>
                    <span className="t-mono-l ml-auto text-ink-1">
                      {formatAmount(balance.balance_value, balance.balance_unit)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Plan history</h3>
            {serviceQuery.data.plan_changes.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                No plan changes recorded. Written when an authorised CHANGE_PLAN action completes.
              </p>
            ) : (
              <ul className="mt-sp-5">
                {serviceQuery.data.plan_changes.map((change) => (
                  <li
                    key={change.change_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <span className="t-body text-ink-2">
                      {change.from_plan ?? "—"} → {change.to_plan}
                    </span>
                    <span className="t-caption text-ink-4">
                      {changedByLabel(change.changed_by)}
                    </span>
                    <span className="t-caption text-ink-4">{change.msisdn ?? "—"}</span>
                    <span className="t-caption ml-auto text-ink-4">
                      {change.effective_date ?? "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Service actions</h3>
            {serviceQuery.data.events.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                No service actions recorded. Top-ups, SIM cases, SIM orders and provisioning
                requests are projected from authorised actions.
              </p>
            ) : (
              <ul className="mt-sp-5">
                {serviceQuery.data.events.map((event) => (
                  <li
                    key={event.event_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <StatusChip status={serviceEventStatusKey(event)} />
                    <span className="t-body text-ink-2">{serviceEventTitle(event)}</span>
                    <span className="t-caption text-ink-4">{event.msisdn ?? "—"}</span>
                    <span className="t-caption text-ink-4">
                      {formatInstant(event.occurred_at)}
                    </span>
                    <span className="t-mono-l ml-auto text-ink-1">
                      {event.source === "recharge"
                        ? formatAmount(event.amount)
                        : (event.reference ?? "—")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {serviceQuery.data.events.length >= LEDGER_CAP ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                Showing the latest {LEDGER_CAP} service actions.
              </p>
            ) : null}
          </section>
        </>
      )}
```

> `LEDGER_CAP` is the constant you already added for FEATURE_16 (value 50, matching `_SERVICE_LIMIT`).
> Reuse it rather than declaring a second constant with the same value. If you would rather the two caps be
> independently named, declare `const SERVICE_CAP = 50` beside it — either is consistent; do not hardcode `50`
> in JSX.
>
> The recharge branch uses `formatAmount(event.amount)` with the default `"TND"`: `ocs.recharges` has no
> currency column, exactly like `billing.payment_plans` (D16.6).
>
> `bonus_amount` is returned but deliberately not rendered — the projection never sets it (always 0), so a
> "+0.00 bonus" on every row would be noise. It is in the payload for when a real recharge channel writes it.

### 4.7 State matrix

| State | Rendered |
| --- | --- |
| Loading | `<CardSkeleton lines={3} />` in `mt-sp-7` |
| 404 | Nothing — the 360 `EmptyState` owns that message |
| Error | `<ErrorState title="Service actions unavailable" onRetry>`; 360 + ledger keep rendering |
| Success, all empty | Three sections, each with its honest caption |
| Success, rows | Balances (chip / type / msisdn / expiry / value) · Plan history (from → to, no chip) · Service actions (chip / title / msisdn / instant / amount-or-reference) |

### 4.8 Design decisions (D17.x)

| # | Decision | Reason |
| --- | --- | --- |
| **D17.1** | New endpoint, not a widened `/ledger` or `/360` | Same as D16.1 — widening a shipped method changes existing behaviour. |
| **D17.2** | Scope through subscriptions, not `customer_id` alone | Two tables have no `customer_id`; two more allow NULL. A customer-id filter would silently under-report. |
| **D17.3** | Three sections, not one merged timeline | Balances are state (no event time); plan changes have **no status column**. Merging would force a fabricated status onto plan changes. |
| **D17.4** | Plan-change rows carry **no** `StatusChip` | There is nothing to map. Precedent: `decision-view.ts` — *"verdicts are decision outcomes, not lifecycle statuses. Token display; never a chip."* |
| **D17.5** | Normalise 4 tables into `events[]` **server-side** | Merging + chronological ordering is a query concern. `source` is returned on every row so provenance is never lost, and the TS union is discriminated on it. |
| **D17.6** | `balance_value` displayed via `formatAmount(value, unit)` | Reuses the existing helper; passes `balance_unit` where a currency goes, giving "42.50 TND" / "12.00 GB". Rounds a `Numeric(14,4)` column to 2 dp for display only. |
| **D17.7** | `parameters` (JSONB) not returned | `/decisions` exposes action parameters to **superviseur**; this route is **conseiller**. Same payload, lower rank = privilege inversion. |
| **D17.8** | `policy_verdict_id` omitted | D16.8 precedent — no `/decisions?verdict=` param exists; a link would be fabricated. |
| **D17.9** | `identity_verified` not rendered | `_sim_case` hardcodes `True`. A constant is not evidence. |
| **D17.10** | Plan changes may appear twice (here and as a provisioning event) | `_provisioning` genuinely writes two unlinked rows. Suppressing one would require a fabricated join. See §6.C. |
| **D17.11** | Cap 50 per collection **and** 50 on the merged list, with caption | Matches FEATURE_16's operator-confirmed "cap + caption". |

---

## 5. Validation checklist

Use **`git grep`** (`rg` is absent from your PATH).

### Backend
| # | Check | Expected |
| --- | --- | --- |
| 1 | `python -m ruff check apps/business-api/src/business_api/repositories.py` | All checks passed (3 new imports alphabetised — no `I001`) |
| 2 | `python -m ruff check apps/business-api/src/business_api/main.py` | **7 pre-existing** (I001 + 6× B904), count unchanged |
| 3 | `python -m pytest apps/business-api/tests -q` | **26 passed** (25 baseline + 1 new, §5.1) |
| 4 | `git diff --stat -- services/ infra/ packages/` | empty — no projection, model or migration touched |
| 5 | `git diff -- apps/business-api/src/business_api/security.py` | empty |
| 6 | `git grep -n "national_id" apps/business-api/src/business_api/repositories.py` | only the pre-existing `customer_list` docstring |
| 7 | `git grep -n "parameters" apps/business-api/src/business_api/repositories.py` | **no hit inside `customer_service_actions`** (D17.7) |
| 8 | `git diff -- main.py` | only the new route; no CORS hunk |
| 9 | `docker compose build business-api && up -d` | image rebuilt, container healthy |
| 10 | `curl -H "X-Role: conseiller" .../customers/<id>/service-actions` | `200`, shape `{customer_id, balances[], plan_changes[], events[]}` |
| 11 | same with a random UUID | `404 {"detail":"customer not found"}` |
| 12 | same with `X-Role: agent` | `403 {"detail":"requires role >= conseiller"}` |
| 13 | Pick a customer with a prepaid line | `balances[]` **non-empty** — the real end-to-end proof (§1.4) |

### Frontend
| # | Check | Expected |
| --- | --- | --- |
| 14 | `node node_modules\typescript\bin\tsc --noEmit` | exit 0 (the discriminated union must narrow — `event.amount` only reachable in the `recharge` branch) |
| 15 | `npx eslint .` | 0 errors, **exactly 9** warnings |
| 16 | `npm run build` | exit 0 |
| 17 | `npx prettier --write` on touched files only | exit 0 |
| 18 | `git diff -- src/lib/nexus/status.ts` | empty |
| 19 | `git diff --stat -- package.json` | empty |
| 20 | `git diff --stat -- src/routes/` | only FEATURE_15's `callbacks.tsx` |
| 21 | `git grep -nE "rgb\(\|#[0-9a-fA-F]{3,6}" src/components/nexus/customer-detail.tsx src/lib/nexus/customer-view.ts` | no hits |
| 22 | `git grep -nE "toLocaleString\(\|new Date\(\|getDay\(\|getHours\(" src/components/nexus/customer-detail.tsx` | no hits |
| 23 | Every new class string appears elsewhere in `customer-detail.tsx` | true |
| 24 | Every `StatusChip` maps every enum: 3 balance + 3 recharge + 5 sim_case + 4 sim_order + 4 provisioning | all into the 28 keys, `?? "open"` / `?? "inactive"` fallbacks |
| 25 | No chip rendered on plan-change rows | true (D17.4) |
| 26 | Overlay portal | inherited unmodified from `modal.tsx` |
| 27 | Zero direct browser requests to `:8108` | true |
| 28 | **Verify `formatAmount` concatenates its second argument** — `git grep -n -A6 "export function formatAmount" src/lib/nexus/customer-view.ts` | It must render `"<number> <unit>"`. If it does anything currency-specific, add a 3-line `formatBalance(value, unit)` beside it instead of passing a unit into a currency slot. |

### 5.1 New test — `apps/business-api/tests/test_customer_service_actions.py`

One deterministic test, no fixtures beyond `db_session`, **no `Customer` insert** — `Customer.national_id`
is `nullable=False` (the lesson from FEATURE_16 §5.1):

```python
"""Contract test for the additive service-actions read."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from business_api.repositories import SupervisionRepository


def test_customer_service_actions_unknown_customer_returns_none(db_session: Session) -> None:
    """Mirrors customer_360 / customer_ledger: a missing customer yields None so the route 404s."""
    repo = SupervisionRepository(db_session)
    assert repo.customer_service_actions(str(uuid4())) is None
```

**Baseline moves 25 -> 26 passed.**

---

## 6. Ambiguities requiring your confirmation before implementation

**A. Modal length.** After this patch the 360 modal has **nine** sections (Subscriptions, Open invoices,
Tickets, Payments, Deferral plans, Consent captures, Live balances, Plan history, Service actions) inside a
520px panel. `modal.tsx`'s scrim is `overflow-y-auto`, so it scrolls correctly — but it is a long scroll.
Options: (i) accept it, (ii) wrap the three new sections in `<details>` toggles — **but I found no `<details>`
precedent in `components/nexus/`, so that would be inventing a pattern**, (iii) defer to a future tabbed-modal
cookbook (rejected as invention in D16.3). **My recommendation: (i) accept.** Confirm.

**B. SIM orders never leave "Requested".** `_sim_order` writes `status="requested"` and **nothing in the
repository ever advances it** to shipped/activated/cancelled. There is no fulfilment write path. That is a
backlog finding, not something to build here (constraint 3). Confirm you want it flagged only — or should I
add a short honesty caption under the section saying orders are not tracked past creation?

**C. The `_provisioning` double-write (§1.3).** A CHANGE_PLAN legitimately shows in both *Plan history* and
*Service actions*. Options: (i) show both, as specified — they answer different questions; (ii) filter
`action_type == "CHANGE_PLAN"` out of `events[]` so plan changes live only in *Plan history*, at the cost of
hiding the provisioning request's own status. **My recommendation: (i).** Confirm.

**D. Balances for postpaid lines.** `ocs` is the prepaid schema. A postpaid-only customer will show an empty
*Live balances* section. Should the caption distinguish "this customer has no prepaid line" from "no balance
rows"? Doing it properly means reading `Subscription.plan_type` (already loaded in the method — one extra
field in the response). Cheap and more honest; say the word and I will fold it in.

**E. Confirm this closes the projection surface.** With FEATURE_16 + FEATURE_17, every table written by
`projections.py` is now readable except `billing.Account` and `billing.Notification`. `Account` is largely
implied by the invoices already shown; `Notification` (sms/whatsapp/email sends) is a genuinely separate
narrative and a natural FEATURE_18. Want it queued?

---

## 7. Files touched — summary

| File | Type | Change |
| --- | --- | --- |
| `apps/business-api/src/business_api/repositories.py` | modified | +3 import lines, +`_SERVICE_LIMIT`, +`customer_service_actions()` |
| `apps/business-api/src/business_api/main.py` | modified | +1 GET route (no CORS hunk) |
| `apps/business-api/tests/test_customer_service_actions.py` | **new** | 1 contract test |
| `Frontend/admin_dashboard/src/lib/api/customers.server.ts` | modified | +7 types, +1 server fn |
| `Frontend/admin_dashboard/src/lib/nexus/query-keys.ts` | modified | +1 key |
| `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts` | modified | +1 type import, +4 status maps, +7 helpers |
| `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx` | modified | +imports, +1 query, +1 guard, +3 sections |

**Never touched:** `status.ts` · `src/routes/*` · `package.json` · `services/` · `packages/` · `infra/` · any
migration · any write path · `projections.py` · `Frontend/customer_portal` · `apps/client-widget`.

**Deployment:** rebuild + recreate the `business-api` container (its Dockerfile bakes the source).
