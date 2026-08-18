# Cookbook 9 - Honest pagination and the data the portal already fetches but never shows

**Target branch:** version_94 (cut from version_93 @ 192c969c35679cdf76f6145e4f0e1776a9abdf5c)
**Backend touched:** `me_reads.py` (3 functions gain a total count and a real offset), `main.py` (3 route signatures gain `offset`)
**New dependencies:** none. **Migrations:** none. **New tables, columns, models:** none.
**Apply after CB8.**

Two distinct problems, one root cause: the API returns less than the UI is built to display.

1. `Pagination` shipped in CB4 and works, but only two of the six list endpoints return the `total`/`limit`/`offset` triple it needs. Billing invoices are hard-capped at 200 rows with no page control; notifications and callbacks discard offset entirely.
2. `/me/balance` returns every balance type plus the last 50 recharges. Services renders **only** `balance_type === "data"` in GB/MB. For a prepaid customer the single most important number - main credit in TND - is fetched, sits in the query cache, and is never drawn.

---

## 9.1 The pagination contract, stated once

`conversations()` and `requests()` already do this correctly, and their shape is the contract:

```python
    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": items,
    }
```

The frontend mirror already exists in `lib/api/activity.server.ts`:

```ts
export type Paged<T> = { total: number; limit: number; offset: number; items: T[] };
```

Everything below simply extends that same shape to invoices, notifications and callbacks. No new type, no new helper, no new convention.

Why `total` matters and a `hasMore` boolean would not: `Pagination` renders "page 1 / 2 / 3" indicators at the bottom, which was an explicit design requirement. Page numbers cannot be derived from a cursor. `total` is the reason the design works.

---

## 9.2 Backend - `me_reads.billing()` gains paged invoices

### What is wrong now

`billing()` returns `accounts`, `total_outstanding`, `currency_code`, `invoices`, `payments`, where `invoices` is a fixed `_LIST_MAX` (200) slice with no count and no offset. `total_outstanding` is computed from that same slice, which is also why it must **stay** unpaged: it is a whole-account figure and paging it would make it wrong.

So the fix is deliberately asymmetric. Keep the account summary global; page only the invoice list.

### Signature

```python
async def billing(
    session: AsyncSession,
    customer_id: UUID,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
```

### The outstanding total must be computed from the database, not from the page

This is the one subtle part. Today `total_outstanding` sums the fetched rows. Once the fetch is one page, that sum becomes "outstanding on this page", which is a wrong number shown next to a right one. Replace it with an aggregate over all of the customer's invoices, and count the invoices in the same pass.

Insert before the invoice list query, using the same `account_ids` the function already derives:

```python
    # Whole-account figures must not follow the invoice page: an outstanding
    # balance computed from 20 visible rows would understate what is owed.
    # _EXCLUDED_OUTSTANDING keeps the existing semantics (paid and void do not
    # count) - it is the same filter the old in-Python sum used.
    totals_stmt = select(
        func.count(Invoice.id),
        func.coalesce(
            func.sum(
                case(
                    (
                        Invoice.status.notin_(_EXCLUDED_OUTSTANDING),
                        Invoice.outstanding_amount,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
    ).where(Invoice.billing_account_id.in_(account_ids))
    invoice_total, outstanding_sum = (await session.execute(totals_stmt)).one()
```

Declare the excluded set next to the module's other constants (it replaces the inline literal that exists today):

```python
# Statuses that owe nothing. Kept as a module constant so the aggregate and any
# future per-row rendering cannot drift apart.
_EXCLUDED_OUTSTANDING = ("paid", "void")
```

Add `case` to the SQLAlchemy import line:

```python
from sqlalchemy import Select, case, func, select
```

### The invoice query gains the page window

Replace the invoice list limit:

```python
        .limit(_LIST_MAX)
```

with:

```python
        .offset(start)
        .limit(size)
```

and resolve the window at the top of the function exactly as `conversations()` does:

```python
    size, start = _page(limit, offset)
```

### The return value

```python
    return {
        "accounts": accounts,
        # Account-wide, deliberately independent of the invoice page below.
        "total_outstanding": _num(outstanding_sum) or 0.0,
        "currency_code": currency_code,
        "invoices": {
            "total": int(invoice_total or 0),
            "limit": size,
            "offset": start,
            "items": invoices,
        },
        # Payments stay a short unpaged recent list: they are context for the
        # invoices, not a browsable ledger. Capped by _LIST_MAX as before.
        "payments": payments,
    }
```

**This is a breaking shape change for one field.** `invoices` goes from an array to a paged object. It is safe here because exactly one consumer exists (`routes/_portal/billing.tsx`, updated in 9.5) and no external client is on these routes yet. Do not do the same to `payments`.

---

## 9.3 Backend - `notifications()` and `callbacks()` gain real windows

Both currently do:

```python
    size, _ = _page(limit, 0)
```

which accepts a limit and throws the offset away, so page 2 is unreachable.

For each of the two functions, change the signature to:

```python
async def notifications(
    session: AsyncSession,
    customer_id: UUID,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
```

replace the window line with:

```python
    size, start = _page(limit, offset)
```

add a count over the same predicate the list query uses - for `notifications()`:

```python
    total = await session.scalar(
        select(func.count(NotificationLog.id)).where(
            NotificationLog.customer_id == customer_id
        )
    )
```

and for `callbacks()`:

```python
    total = await session.scalar(
        select(func.count(CallbackRequest.id)).where(
            CallbackRequest.customer_id == customer_id
        )
    )
```

The count predicate must be **identical** to the list predicate, or the page indicators will promise pages that render empty. If either list query carries an extra filter, copy it into the count.

Apply the window to each list query:

```python
        .offset(start)
        .limit(size)
```

and return the standard shape:

```python
    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": items,
    }
```

---

## 9.4 Backend - route signatures in `main.py`

The three `/me/*` routes that call the functions above take `limit` only. Add `offset` with the same validation the paged routes already use, and keep passing the client principal's customer id through the existing `_client_customer_id()` helper - do not introduce a second way to resolve the customer.

```python
@app.get("/api/v1/me/billing")
async def me_billing(
    principal: Annotated[Principal, Depends(require_client)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return await me_reads.billing(
        session, _client_customer_id(principal), limit=limit, offset=offset
    )
```

Apply the identical two-line addition to `me_notifications` and `me_callbacks`. Nothing else in `main.py` changes: no new dependency, no new guard, no change to `require_client`, no change to `_ROLE_RANK`.

---

## 9.5 Frontend - server functions

### `lib/api/billing.server.ts`

Mirror the new shape and accept the window. Import the shared `Paged` type rather than redeclaring it:

```ts
import type { Paged } from "./activity.server";
import { z } from "zod";

export type BillingPayload = {
  accounts: BillingAccount[];
  total_outstanding: number;
  currency_code: string;
  /** Paged: the account figures above are whole-account and do not follow it. */
  invoices: Paged<InvoiceItem>;
  payments: PaymentItem[];
};

export const fetchBilling = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<BillingPayload>(
      `/api/v1/me/billing?limit=${data.limit}&offset=${data.offset}`,
      {},
    ),
  );
```

### `lib/api/notifications.server.ts`

```ts
export const fetchNotifications = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<Paged<NotificationItem>>(
      `/api/v1/me/notifications?limit=${data.limit}&offset=${data.offset}`,
      {},
    ),
  );
```

### `lib/api/activity.server.ts` - callbacks

```ts
export const fetchCallbacks = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<Paged<CallbackItem>>(
      `/api/v1/me/callbacks?limit=${data.limit}&offset=${data.offset}`,
      {},
    ),
  );
```

### `lib/query-keys.ts`

Three keys gain the window, matching the existing `conversations`/`requests` pattern. Keys without a window would cache page 2 over page 1.

```ts
  billing: (cid: string, limit: number, offset: number) =>
    ["me", cid, "billing", limit, offset] as const,
  notifications: (cid: string, limit: number, offset: number) =>
    ["me", cid, "notifications", limit, offset] as const,
  callbacks: (cid: string, limit: number, offset: number) =>
    ["me", cid, "callbacks", limit, offset] as const,
```

The `["me", cid, ...]` prefix is preserved, so CB8's post-call invalidation still sweeps all of them.

---

## 9.6 Frontend - Billing and Notifications get real page controls

The pattern is already proven in `activity.tsx` and `requests.tsx`. Reuse it verbatim rather than inventing a second one.

In `routes/_portal/billing.tsx`:

```tsx
const PAGE_SIZE = 20;

  const [page, setPage] = useState(0);
  const billingQuery = useQuery({
    queryKey: qk.billing(customerId, PAGE_SIZE, page * PAGE_SIZE),
    queryFn: () => fetchBilling({ data: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } }),
    // Keeps the previous page on screen while the next one loads, which is what
    // makes CB8's isPlaceholderData dim meaningful instead of a blank flash.
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
```

Read the list from the paged object, and the summary tiles from the account-wide fields:

```tsx
  const invoices = billingQuery.data?.invoices.items ?? [];
  const invoiceTotal = billingQuery.data?.invoices.total ?? 0;
```

Render the control under the invoice list, inside the same `DataSection`:

```tsx
          <Pagination
            total={invoiceTotal}
            limit={PAGE_SIZE}
            offset={page * PAGE_SIZE}
            onPage={(next) => setPage(next)}
          />
```

Apply the identical treatment to the notifications list (wherever it renders - Activity or its own section) and to callbacks.

**Reset the page when a filter changes.** Any screen that combines a filter with pagination must `setPage(0)` in the filter's handler, otherwise a filter narrowing the result set leaves the customer stranded on an empty page 3:

```tsx
  const onFilterChange = (next: string | undefined) => {
    setStatus(next);
    setPage(0); // a narrower filter can have fewer pages than the current one
  };
```

Verify this on `requests.tsx` too - it already has both a status filter and pagination, and this reset is the one thing that combination gets wrong most often.

---

## 9.7 Services shows everything `/me/balance` returns

### The rule

Render every balance the API returns, grouped by type, with the unit the API gives. Do not filter by type in the UI. `me_reads.balance()` already returns only the signed-in customer's rows.

Replace the `isDataBalance` filter entirely with a grouping:

```tsx
// The API returns main credit, data, voice and SMS. Filtering to data only
// meant a prepaid customer never saw their credit - the number they open the
// portal for. Order is presentation priority, not API order.
const BALANCE_ORDER: Array<BalanceItem["balance_type"]> = ["main", "data", "voice", "sms"];

function groupBalances(items: BalanceItem[]) {
  return BALANCE_ORDER.map((type) => ({
    type,
    label: copy.services.balanceTypes[type],
    items: items.filter((b) => b.balance_type === type),
  })).filter((group) => group.items.length > 0);
}
```

Add the labels to `lib/copy.ts` under `services` (customer wording, no schema words):

```ts
    balanceTypes: {
      main: "Credit",
      data: "Data",
      voice: "Calls",
      sms: "Messages",
    },
    recharges: "Recent top-ups",
    rechargesEmpty: "No top-ups in the last few months.",
```

### Formatting must follow the unit, not assume one

`lib/format.ts` already exposes the TND currency formatter and the locale number formatter. Use the currency formatter only for `TND`:

```tsx
function balanceValue(item: BalanceItem) {
  if (item.value == null) return "-";
  // TND is money and must carry the currency code; GB/MB/MIN/SMS are counts and
  // must not be formatted as money.
  return item.unit === "TND" ? currency(item.value) : `${number(item.value)} ${item.unit}`;
}
```

### Recharges become a real section

`recharges` is fetched on every Services load today and discarded. It is the answer to "did my top-up go through", which is a top-three self-service question, and it needs no new endpoint:

```tsx
        <DataSection
          label={copy.services.recharges}
          state={balanceQuery}
          empty={copy.services.rechargesEmpty}
          onRetry={() => void balanceQuery.refetch()}
        >
          <ul className="divide-y divide-stroke-subtle">
            {recharges.map((r, i) => (
              <li key={`${r.created_at ?? "na"}-${i}`} className="flex items-baseline justify-between gap-sp-4 py-sp-3">
                <div className="min-w-0">
                  <p className="t-body text-ink-1">{currency(r.amount ?? 0)}</p>
                  <p className="t-caption text-ink-4">
                    {copy.services.rechargeChannels[r.channel]}
                    {r.bonus_amount ? ` - includes ${currency(r.bonus_amount)} bonus` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <StatusPill status={r.status} />
                  <p className="t-caption text-ink-4">{dateTime(r.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        </DataSection>
```

with the channel wording in `copy.ts` - never render the raw enum:

```ts
    rechargeChannels: {
      app: "Mobile app",
      web: "Online",
      ussd: "USSD",
      scratch_card: "Scratch card",
      agent: "In store",
    },
```

A failed recharge with no explanation is worse than none. If `status === "failed"`, the pill must be accompanied by the neutral line already used elsewhere for terminal failures - do not invent a reason the API does not return.

The full spatial layout of the rebuilt Services page is in `10-tabs-organisation-and-visibility.md` 10.4; this section defines only what data it draws.

---

## 9.8 Acceptance checks

| # | Check | How | Pass condition |
|---|---|---|---|
| 1 | Invoice paging works | seed >20 invoices, open /billing | page indicators appear; page 2 shows different invoices |
| 2 | Outstanding is account-wide | compare the tile on page 1 and page 2 | identical on every page |
| 3 | Outstanding is correct | `SELECT sum(outstanding_amount) FROM billing.invoices WHERE status NOT IN ('paid','void') AND billing_account_id IN (...)` | matches the tile exactly |
| 4 | Notifications page | seed >20 notifications | page 2 reachable and non-empty |
| 5 | Callbacks page | seed >20 callbacks | page 2 reachable and non-empty |
| 6 | Count matches list | for each of the three, compare `total` to a `count(*)` with the same predicate | equal |
| 7 | No phantom page | set limit to exactly `total` | one page indicator only |
| 8 | Filter resets page | on /requests go to page 2, change status | back on page 1, list non-empty |
| 9 | Cache is not shared across pages | page 1 -> 2 -> 1 | page 1 rows identical to the first visit |
| 10 | Prepaid credit visible | sign in as the prepaid pilot customer | main credit in TND is on /services above data |
| 11 | Units are honest | inspect each balance row | TND carries the code; GB/MB/MIN/SMS never formatted as money |
| 12 | Recharges render | seed a completed and a failed top-up | both listed with customer wording, newest first |
| 13 | No raw enums | `grep -Rn "scratch_card\|balance_type" src/routes` | zero hits outside type positions |
| 14 | Client cannot widen scope | `curl` `/api/v1/me/billing?limit=999` with a client token | 422 from the `le=50` guard, not 200 |
| 15 | Cross-customer isolation | two client tokens, same route | disjoint invoice sets; no customer id accepted from the client |
| 16 | Types clean | `npm run typecheck` | zero errors |
| 17 | Backend clean | `ruff check apps/business-api` and `mypy apps/business-api` | zero new findings |

### Rollback

| Change | Revert | Consequence |
|---|---|---|
| 9.2 paged invoices | restore the flat `invoices` array and the in-Python sum, revert `billing.tsx` together | must revert both sides at once - this is the only breaking shape change in the batch |
| 9.3 / 9.4 | drop `offset` from the signatures and the routes | lists fall back to page 1 only; no other breakage |
| 9.7 Services depth | restore `isDataBalance` | prepaid credit and recharges disappear again |
