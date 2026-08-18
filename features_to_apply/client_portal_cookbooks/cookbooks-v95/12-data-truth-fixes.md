# Cookbook 12 - Data truth fixes

**Target branch:** version_95 (cut from version_94 @ 48004d601f6eec165e26fc3d956f573d7b4636ec)
**Files modified:** 5 - `me_reads.py`, `billing.server.ts`, `billing.tsx`, `profile.tsx`, `data.tsx`
**New dependencies:** none. **Migrations:** none. **Advisor projections widened:** none. **Model edits:** none.

Every item here is a case of the portal telling the customer something that is not true. None of it is cosmetic. Apply in order; 12.1 is the one that corrupts data the customer reads.

---

## 12.1 `notifications()` and `callbacks()` ignore the offset they report

### What is wrong

On version_94, both functions compute the window and then never apply it:

```python
    size, start = _page(limit, offset)
    ...
        .order_by(Notification.created_at.desc())
        .limit(size)
    ).all()
    return {"total": ..., "limit": size, "offset": start, "items": items}
```

The envelope advertises `offset: 20` while the rows are `offset 0`. Any UI that trusts the contract - and `Pagination` is built to trust it - renders page 2, 3 and 4 as identical lists. The route accepting `offset` without a 422 is what was verified; that is a different assertion from honouring it.

### Fix

In `apps/business-api/src/business_api/me_reads.py`, `notifications()`:

```python
    rows = session.execute(
        select(
            Notification.id,
            Notification.channel,
            Notification.template_code,
            Notification.status,
            Notification.sent_at,
            Notification.created_at,
        )
        .where(Notification.customer_id == customer_id)
        .order_by(Notification.created_at.desc(), Notification.id.asc())
        .offset(start)
        .limit(size)
    ).all()
```

and in `callbacks()`:

```python
    rows = session.execute(
        select(
            CallbackSchedule.id,
            CallbackSchedule.scheduled_time,
            CallbackSchedule.preferred_window,
            CallbackSchedule.status,
            CallbackSchedule.reason,
            CallbackSchedule.completed_at,
        )
        .where(CallbackSchedule.customer_id == customer_id)
        .order_by(CallbackSchedule.scheduled_time.desc(), CallbackSchedule.id.asc())
        .offset(start)
        .limit(size)
    ).all()
```

### Why the `id` tiebreak is part of the fix, not extra scope

`OFFSET` without a total order is undefined across pages. 48 seeded notifications include rows created in the same transaction with identical `created_at` to the second; Postgres may order them differently between the page-1 and page-2 queries, so a row can appear twice or never. Adding `Notification.id.asc()` makes the sort total and the paging stable. `conversations()` and `requests()` order by a timestamp that is effectively unique per row, so they are left alone in this cookbook - but if you ever see a duplicate row across pages there, the same one-line remedy applies.

### Also apply the same total order to the count

Nothing to change: `func.count()` is order-independent. The counts already use the same `WHERE` predicate as the list query, which is the property that matters, and both are correct on version_94.

---

## 12.2 The due date under "Amount due" must be account-wide

### What is wrong

`billing.tsx` derives it from the visible page:

```tsx
  const nextDue = useMemo(() => {
    const dues = invoices.filter((i) => i.status !== "paid" && i.status !== "void")...
```

CB9 deliberately kept `total_outstanding` independent of the page. The hint rendered directly beneath it is not, so paging changes the date under a total that does not move.

### Fix - one additive field, computed where the other account-wide figure is computed

In `me_reads.billing()`, extend the existing totals statement rather than adding a query:

```python
    # Whole-account figures must not follow the invoice page: an outstanding
    # balance or a next-due date computed from 20 visible rows would misstate
    # what is owed and when.
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
        # Earliest due date still owing, across every account invoice.
        func.min(
            case(
                (
                    Invoice.status.notin_(_EXCLUDED_OUTSTANDING),
                    Invoice.due_date,
                ),
                else_=None,
            )
        ),
    ).where(Invoice.billing_account_id.in_(account_ids))
    invoice_total, outstanding_sum, next_due_date = session.execute(totals_stmt).one()
```

Add it to the returned envelope next to the value it qualifies:

```python
        # Account-wide, deliberately independent of the invoice page below.
        "total_outstanding": _num(outstanding_sum) or 0.0,
        "next_due_date": _iso(next_due_date),
        "currency_code": currency_code,
```

and to the empty-account early return so the shape never varies:

```python
        return {
            "accounts": [],
            "total_outstanding": 0.0,
            "next_due_date": None,
            "currency_code": "",
            "invoices": {"total": 0, "limit": size, "offset": start, "items": []},
            "payments": [],
        }
```

Type it in `Frontend/customer_portal/src/lib/api/billing.server.ts`, in `BillingPayload`:

```ts
  total_outstanding: number;
  /** Earliest unpaid due date across every account invoice - not the page. */
  next_due_date: string | null;
  currency_code: string;
```

Then in `billing.tsx` delete the `useMemo` entirely, drop the now-unused `useMemo` import, and use the server value:

```tsx
          <MetricTile
            size="xl"
            label={copy.billing.amountDue}
            value={money(billing.total_outstanding, billing.currency_code)}
            hint={billing.next_due_date ? date(billing.next_due_date) : undefined}
          />
```

---

## 12.3 `billing.tsx` must stop replacing the page

The file builds a correct `DataSection` for invoices and then makes it unreachable:

```tsx
  if (billingQuery.isPending || balanceQuery.isPending) { return ( <full-page skeleton> ); }
  if (billingQuery.isError || !billing) { return ( <Card><ErrorState /></Card> ); }
```

The second condition is defensible only because `billing` is used unguarded below. The first is not: the invoice list waits on the **balance** query, which it does not consume, so one slow prepaid read blanks the whole page.

### Fix

Delete both blocks. Replace the tile and the balance sections with per-section states.

The headline tile, which must render a shape immediately:

```tsx
      <PageSection>
        <Card>
          {billingQuery.isError ? (
            <ErrorState error={billingQuery.error} onRetry={() => void billingQuery.refetch()} />
          ) : (
            <MetricTile
              size="xl"
              pending={billingQuery.isPending}
              label={copy.billing.amountDue}
              value={billing ? money(billing.total_outstanding, billing.currency_code) : ""}
              hint={billing?.next_due_date ? date(billing.next_due_date) : undefined}
            />
          )}
        </Card>
      </PageSection>
```

Every later read of `billing` becomes optional, which the file is already written for (`billing?.invoices.items ?? []`). Two derived flags change:

```tsx
  // Postpaid is unknown until the payload lands. Rendering the invoice section
  // during load is correct: DataSection owns the skeleton, and a customer with
  // no accounts sees it collapse once, not a page that rebuilds itself.
  const postpaid = billing ? billing.accounts.length > 0 : true;
  const hasBalances = balance.balances.length > 0;
```

And the "nothing at all" card must not fire while either query is still loading:

```tsx
      {!billingQuery.isPending && !balanceQuery.isPending && !postpaid && !hasBalances && (
        <Card>
          <p className="t-caption text-ink-5">{copy.empty.generic}</p>
        </Card>
      )}
```

The `SkeletonList` / `SkeletonMetric` imports become unused - remove them from the import block or the lint step fails.

---

## 12.4 `MetricTile` needs a pending state

Without it, callers pass `"—"` during load, which is indistinguishable from a genuine zero or a genuine blank. In `components/portal/data.tsx`:

```tsx
/** Metric tile - the anti-cramming device: one number, one label, real space. */
export function MetricTile({
  label,
  value,
  hint,
  size = "m",
  /** Shows a shimmer at the value's own type size instead of a placeholder
   *  glyph, so "still loading" is never read as "zero" or "nothing". */
  pending = false,
}: {
  label: string;
  value: string;
  hint?: string | undefined;
  size?: "m" | "l" | "xl";
  pending?: boolean;
}) {
  const type = size === "xl" ? "t-metric-xl" : size === "l" ? "t-metric-l" : "t-metric-m";
  const barHeight = size === "xl" ? "h-10" : size === "l" ? "h-8" : "h-6";
  return (
    <div className="min-w-0">
      <div className="t-micro-2 text-ink-5">{label}</div>
      {pending ? (
        <div
          className={cn("skeleton mt-sp-3 w-32 rounded-r-2", barHeight)}
          role="status"
          aria-busy="true"
          aria-label={copy.common.loading}
        />
      ) : (
        <div className={cn(type, "mt-sp-3 truncate text-ink-1")}>{value}</div>
      )}
      {hint && !pending ? (
        <div className="t-caption mt-sp-2 truncate text-ink-4">{hint}</div>
      ) : null}
    </div>
  );
}
```

The bar heights match the existing type scale so nothing reflows when the number arrives. No new token, no CSS change - `.skeleton` already animates.

---

## 12.5 `profile.tsx` - four fixes

### 12.5.1 Customer-scoped query key and the standard stale window

`query-keys.ts` states the rule: every key carries the signed-in customer id so a different account can never see another account's cached rows. This page opts out, which also hides it from the post-call `["me", customerId]` sweep.

Add the imports:

```tsx
import { usePortalSession } from "@/lib/use-portal-session";
import { qk } from "@/lib/query-keys";
```

and replace the query:

```tsx
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const query = useQuery({
    // Customer-scoped like every other portal read: an unscoped key can serve
    // the previous account's details after a sign-out/sign-in in the same tab.
    queryKey: qk.profileDetail(cid),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });
```

### 12.5.2 Skeleton instead of a sentence, inline error instead of a page swap

Replace both early-return blocks:

```tsx
  if (query.isPending) {
    return (
      <div className="grid gap-sp-7 lg:grid-cols-[200px_1fr]">
        <div className="flex gap-sp-3 lg:flex-col">
          {SECTIONS.map((s) => (
            <SkeletonLine key={s.id} className="h-8 w-24 lg:w-full" />
          ))}
        </div>
        <Card>
          <SkeletonMetric />
          <Divider className="mt-sp-7" />
          <SkeletonList rows={3} />
        </Card>
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      </Card>
    );
  }
```

with imports `import { Divider } from "@/components/portal/primitives";` (already imported) and `import { ErrorState, SkeletonLine, SkeletonList, SkeletonMetric } from "@/components/portal/data";`. The hand-rolled `errorMessage` import and the `Button` retry can go - `ErrorState` covers both, so this page finally reports 401/403/429 the same way every other page does.

The left nav renders as skeleton rails at the same width, so the two-column grid does not jump when data lands.

### 12.5.3 Delete the invented verification badges

These two lines assert facts we do not have:

```tsx
  action={me.email ? <StatusChip tone="outline">VERIFIED</StatusChip> : null}
  action={<StatusChip tone="dashed">UNVERIFIED</StatusChip>}
```

Email is called verified because a string is non-empty. Phone is called unverified unconditionally - including for the MSISDN we bill. There is no verification column behind either claim, so both must go:

```tsx
              <FieldRow label={copy.profile.fields.email} value={me.email ?? "\u2014"} />
              <Divider />
              <FieldRow
                label={copy.profile.fields.phone}
                value={me.phone ?? me.msisdn ?? "\u2014"}
                mono
              />
```

If verification status is wanted later it needs a real column and a real flow; until then silence is accurate and a badge is not. `StatusChip` stays imported only if the VIP removal below leaves another user of it - if not, remove it from the import block.

### 12.5.4 Remove the VIP chip

```tsx
              {me.vip ? <StatusChip tone="solid" className="ml-auto">VIP</StatusChip> : null}
```

VIP tiering is internal commercial segmentation. The portal's own rule keeps supervision and segmentation signals out of customer reads, and `customer_vip` is on the forbidden-key list - this survives only because the projection field is named `vip`. Delete the chip.

Then stop serving the field. In whichever module builds `/me/profile/detail`, drop `vip` from both the SELECT and the returned dict, and remove it from the `ProfileDetail` type in `lib/api/me.server.ts`. Removing a field is a shape change: `git grep -n "\bvip\b" Frontend/customer_portal/src` must return nothing before you commit, otherwise typecheck will tell you where it is still read.

If you decide VIP is a deliberate customer-facing benefit, say so explicitly and keep it - but then it needs its own copy explaining what it grants, not a bare chip.

---

## 12.6 Acceptance checks

| # | Check | Command or action | Pass condition |
|---|---|---|---|
| 1 | Notifications page 2 differs | `GET /api/v1/me/notifications?limit=5&offset=0` then `&offset=5` as a client | no `template_code` + `created_at` pair appears in both responses |
| 2 | Callbacks page 2 differs | same with `/me/callbacks` | disjoint pages |
| 3 | No row lost across pages | walk `offset=0,5,10...` to `total` | union size equals `total`; no duplicates |
| 4 | Counts unchanged | compare `total` before and after | identical values |
| 5 | Due date is account-wide | open /billing, page through invoices | the date under Amount due never changes |
| 6 | Due date matches SQL | `SELECT min(due_date) FROM billing.invoices WHERE billing_account_id IN (...) AND status NOT IN ('paid','void');` | equals `next_due_date` |
| 7 | Empty-account shape stable | client with no billing account | payload contains `next_due_date: null`, no key missing |
| 8 | Slow balance no longer blanks billing | throttle `/me/balance` to 5s, open /billing | tile and invoice list render immediately |
| 9 | Invoice failure is contained | fail only `/me/billing` | inline error in the tile card; balances still render |
| 10 | Tiles shimmer, never lie | open /billing on a cold cache | shimmer at the value's size; no `—` flash |
| 11 | Profile key is scoped | React Query devtools on /profile | key is `["me", <cid>, "profile", "detail"]` |
| 12 | No cross-account bleed | sign in A, open /profile, sign out, sign in B, open /profile | B's name renders; A's never appears |
| 13 | Profile loads without a jump | cold /profile | skeleton nav + card, no text sentence, no reflow |
| 14 | No invented badges | /profile contact section | no VERIFIED / UNVERIFIED chips |
| 15 | VIP gone end to end | `git grep -n "\bvip\b" Frontend/customer_portal/src` and the profile-detail response | zero hits; no `vip` key on the wire |
| 16 | Orb and tokens untouched | `git diff version_94..version_95 -- Frontend/customer_portal/src/styles.css Frontend/customer_portal/src/components/orb` | empty |
| 17 | Gates green | typecheck, lint, test, build, `ruff`, `mypy`, `pytest` | all pass |

### Rollback

| Change | Revert | Consequence |
|---|---|---|
| 12.1 offset | remove `.offset(start)` and the id tiebreak | pagination silently lies again |
| 12.2 `next_due_date` | drop the field and restore the `useMemo` | hint drifts per page; field removal is a shape change, so revert both sides together |
| 12.3 early returns | restore the two blocks | balance latency blanks billing |
| 12.4 `pending` | prop is optional; existing callers unaffected | tiles read `—` as data |
| 12.5 profile | per-hunk, independent | 12.5.4 is a shape change - revert projection and type together |
