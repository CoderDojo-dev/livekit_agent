# Cookbook 13 - Services / Billing boundary, tab organisation and visibility

**Target branch:** version_95 (cut from version_94 @ 48004d601f6eec165e26fc3d956f573d7b4636ec)
**Files modified:** 4 - services.tsx, billing.tsx, help.tsx, copy.ts
**New dependencies:** none. **Backend:** none. **Migrations:** none. **styles.css / components/orb:** untouched.

---

## DECISION REQUIRED BEFORE APPLYING

On version_94 the same prepaid data is rendered in two tabs with different completeness:

| | Billing tab | Services tab |
|---|---|---|
| Balances | **all** types, as cards | data only, as a list |
| Recharges | full list with bonus, channel, timestamp | absent |

One of them has to own it. This cookbook is written for **Option A**, which I recommend:

- **Option A (written below).** Services owns balances and recharges - what you have. Billing owns amount due, invoices and payments - what you owe and what you paid. Rationale: a prepaid customer who never receives an invoice should never need the Billing tab, and how much credit is left is a service question. Billing keeps a one-line prepaid pointer so a hybrid customer is not stranded.
- **Option B.** Billing owns everything with money in it, balances and recharges included; Services becomes plan and subscription only. Rationale: one place for all numbers. Cost: Services is then almost empty, which is the density problem you asked me to fix.

If you prefer B, tell me and I will reissue 13.1 and 13.2 inverted - nothing else in the file changes.

---

## 13.1 Rebuild Services (Option A)

### What is wrong today

services.tsx on version_94 is the version_93 file plus one line. It still filters to data-only, still swaps the whole page for a skeleton, still replaces the page with an error card if the profile read fails, and never shows recharges. CB9 section 9.7 and CB10 section 10.4 were not applied.

### Full replacement

Replace everything below the head block in Frontend/customer_portal/src/routes/_portal/services.tsx.

Imports and helpers:

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem, type RechargeItem } from "@/lib/api/billing.server";
import { date, dateTime, money, quantity } from "@/lib/format";
import { Card, StatusChip } from "@/components/portal/primitives";
import { DataSection, MetricTile, PageSection } from "@/components/portal/data";

/* Balance types in the order a customer thinks about them: money first, then
 * the bundles that money bought. Anything the OCS invents later sorts last
 * instead of vanishing - the version_94 data-only filter is exactly the bug
 * this ordering replaces. */
const BALANCE_ORDER: Array<BalanceItem["balance_type"]> = ["main", "data", "voice", "sms"];

function orderBalances(items: BalanceItem[]): BalanceItem[] {
  return [...items].sort((a, b) => {
    const ai = BALANCE_ORDER.indexOf(a.balance_type);
    const bi = BALANCE_ORDER.indexOf(b.balance_type);
    return (ai < 0 ? BALANCE_ORDER.length : ai) - (bi < 0 ? BALANCE_ORDER.length : bi);
  });
}

/** Main balance is currency; every other type is a metered quantity. */
function balanceValue(item: BalanceItem): string {
  return item.balance_type === "main" && item.unit === "TND"
    ? money(item.value, "TND")
    : quantity(item.value, item.unit);
}
```

Component head - two queries, no early return anywhere:

```tsx
function ServicesScreen() {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const profileQuery = useQuery({
    queryKey: qk.profile360(cid),
    queryFn: () => fetchProfile360(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(cid),
    queryFn: () => fetchBalance(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const subscriptions = profileQuery.data?.subscriptions ?? [];
  const balances = orderBalances(balanceQuery.data?.balances ?? []);
  const recharges = balanceQuery.data?.recharges ?? [];
  const main = balances.find((b) => b.balance_type === "main");
  const activeLines = subscriptions.filter((s) => s.status === "active").length;
```

Row 1 - three tiles, the answer to "how am I doing" above the fold:

```tsx
  return (
    <div className="space-y-sp-9">
      <PageSection>
        <Card>
          <div className="grid gap-sp-7 sm:grid-cols-3">
            <MetricTile
              label={copy.services.tiles.credit}
              value={main ? balanceValue(main) : copy.common.notApplicable}
              hint={main?.expires_on ? copy.services.expires(date(main.expires_on)) : undefined}
              size="xl"
              pending={balanceQuery.isPending}
            />
            <MetricTile
              label={copy.services.tiles.lines}
              value={String(activeLines)}
              hint={
                subscriptions.length > activeLines
                  ? copy.services.tiles.linesHint(subscriptions.length)
                  : undefined
              }
              size="l"
              pending={profileQuery.isPending}
            />
            <MetricTile
              label={copy.services.tiles.plan}
              value={subscriptions[0]?.plan ?? copy.common.notApplicable}
              hint={subscriptions[0]?.msisdn ?? undefined}
              size="l"
              pending={profileQuery.isPending}
            />
          </div>
        </Card>
      </PageSection>
```

Row 2 - the lines themselves:

```tsx
      <DataSection
        label={copy.services.plan}
        state={{
          isPending: profileQuery.isPending,
          isFetching: profileQuery.isFetching,
          isPlaceholderData: profileQuery.isPlaceholderData,
          error: profileQuery.error,
        }}
        items={subscriptions}
        skeletonRows={2}
        empty={{
          title: copy.services.subscriptionsEmpty.title,
          body: copy.services.subscriptionsEmpty.body,
        }}
        onRetry={() => void profileQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((sub) => (
              <Card key={sub.subscription_id}>
                <div className="flex items-start justify-between gap-sp-5">
                  <div className="min-w-0">
                    <div className="t-metric-l truncate text-ink-1">{sub.plan ?? "-"}</div>
                    <div className="t-mono-s mt-sp-4 text-ink-5">{sub.msisdn ?? "-"}</div>
                  </div>
                  {sub.status ? <StatusChip tone="solid">{sub.status}</StatusChip> : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </DataSection>
```

Row 3 - every balance type, not just data:

```tsx
      <DataSection<BalanceItem>
        label={copy.services.balances}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={balances}
        skeletonRows={3}
        empty={{
          title: copy.services.balancesEmpty.title,
          body: copy.services.balancesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2">
            {items.map((b, i) => (
              <div
                key={`${b.msisdn}-${b.balance_type}-${i}`}
                className="rounded-r-3 border border-stroke-subtle p-sp-6"
              >
                <div className="flex items-center justify-between gap-sp-5">
                  <span className="t-micro-2 text-ink-5">
                    {copy.labels.balanceType[b.balance_type] ?? b.balance_type}
                  </span>
                  <StatusChip tone={b.status === "active" ? "outline" : "muted"}>
                    {b.status}
                  </StatusChip>
                </div>
                <div className="t-metric-l mt-sp-5 text-ink-1">{balanceValue(b)}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {b.msisdn ?? "-"}
                  {b.expires_on ? ` / ${copy.services.expires(date(b.expires_on))}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </DataSection>
```

Row 4 - where the credit came from:

```tsx
      <DataSection<RechargeItem>
        label={copy.services.recharges}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={recharges}
        skeletonRows={3}
        empty={{
          title: copy.services.rechargesEmpty.title,
          body: copy.services.rechargesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <ul className="divide-y divide-stroke-subtle">
            {items.map((r, i) => (
              <li
                key={`${r.msisdn}-${r.created_at}-${i}`}
                className="flex items-center justify-between gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <div className="t-body-strong text-ink-1">
                    {money(r.amount)}
                    {r.bonus_amount ? (
                      <span className="t-caption text-ink-4">
                        {" "}
                        {copy.billing.bonus(money(r.bonus_amount))}
                      </span>
                    ) : null}
                  </div>
                  <div className="t-caption mt-sp-1 truncate text-ink-5">
                    {r.msisdn ?? "-"}
                    {" / "}
                    {copy.labels.rechargeChannel[r.channel] ?? r.channel}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="t-ui text-ink-3">{r.status}</div>
                  <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(r.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataSection>
    </div>
  );
}
```

Keep the existing separator glyph the file already uses for these rows rather than the placeholder slash above if you prefer the middle dot; the only rule is that it matches the Billing rows it replaces.

Four things to notice, because they are the rules the rest of the portal should follow:

1. **No early return.** The page shape is fixed at first paint; sections fill in.
2. **No type filter.** An unknown balance type sorts last instead of disappearing.
3. **main is money, everything else is a quantity.** quantity(90.30, "TND") reads as a bundle; money() reads as credit.
4. **Two queries, four sections, four independent failure domains.**

---

## 13.2 Billing gives up balances and recharges

With Services owning them, delete from billing.tsx:

- the `hasBalances && ( <PageSection label={copy.billing.balances}> ... )` block
- the `hasBalances && ( <PageSection label={copy.billing.recharges}> ... )` block
- the now-unused `quantity` and `dateTime` imports, `EmptyState` if nothing else uses it, and copy.billing.balances / recharges / noRecharges if nothing else references them

Keep balanceQuery **only** to decide whether this customer has a prepaid side, and replace both blocks with one pointer so a hybrid customer is never stranded:

```tsx
      {hasBalances && (
        <PageSection>
          <Card className="flex items-center justify-between gap-sp-6">
            <p className="t-caption max-w-md text-ink-4">{copy.billing.prepaidPointer}</p>
            <Link
              to="/services"
              className="focus-ring t-ui shrink-0 rounded-r-2 px-sp-5 py-sp-3 text-ink-2 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
            >
              {copy.billing.prepaidPointerAction}
            </Link>
          </Card>
        </PageSection>
      )}
```

with `import { Link } from "@tanstack/react-router";` added. Combined with CB12 section 12.3, Billing is now exactly: amount due, invoices with pagination, payments, and one line acknowledging prepaid.

---

## 13.3 Help must have an exit

help.tsx closes with a still-stuck card containing text and no action, while importing Button and never using it. The page whose only job is to route a stuck customer routes them nowhere.

```tsx
      <Card className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-sp-6">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
            <LifeBuoy size={16} strokeWidth={1.5} />
          </span>
          <div>
            <div className="t-micro text-ink-5">{copy.help.stillStuck}</div>
            <p className="t-body mt-sp-3 max-w-xl text-ink-3">{copy.help.contactBody}</p>
          </div>
        </div>
        {/* Two real exits, in the order most customers want them. */}
        <div className="flex shrink-0 gap-sp-4">
          <Link to="/assistant">
            <Button>{copy.help.talkToAssistant}</Button>
          </Link>
          <Link to="/requests">
            <Button variant="secondary">{copy.help.openRequest}</Button>
          </Link>
        </div>
      </Card>
```

The action line inside each topic card is also invisible until hover, which hides it from touch users entirely. Make it always legible and let hover carry only the emphasis:

```tsx
                  <span className="t-caption mt-sp-2 block text-ink-5 transition-colors group-hover:text-ink-3">
                    {t.action}
                  </span>
```

---

## 13.4 Copy keys

Add to lib/copy.ts under services, and delete the dead keys the version_94 patch introduced (services.balanceTypes, services.rechargeChannels) - copy.labels.balanceType and copy.labels.rechargeChannel are the real homes and are already used:

```ts
  services: {
    // ...existing keys stay
    tiles: {
      credit: "Credit",
      lines: "Active lines",
      linesHint: (total: number) => `of ${total} total`,
      plan: "Plan",
    },
    expires: (on: string) => `expires ${on}`,
    recharges: "Top-ups",
    balancesEmpty: {
      title: "No balances yet",
      body: "Balances appear here once your line is active. If you expect credit, ask the assistant to check the line.",
    },
    rechargesEmpty: {
      title: "No top-ups yet",
      body: "Top-ups you make by app, web, USSD, scratch card or at an agent appear here with any bonus credit.",
    },
    subscriptionsEmpty: {
      title: "No lines on this account",
      body: "If you have a line that is missing here, open a request and we will connect it to your account.",
    },
  },
```

under billing:

```ts
    prepaidPointer: "Your prepaid credit, bundles and top-ups live in Services.",
    prepaidPointerAction: "Open Services",
```

under help:

```ts
    talkToAssistant: "Talk to the assistant",
    openRequest: "Open a request",
```

and under common, if it is not already there:

```ts
    notApplicable: "-",
```

Use the same em-dash glyph the rest of copy.ts already uses for notApplicable rather than a hyphen.

Every empty state names a next step. "No data" is not an empty state; it is an unanswered question.

---

## 13.5 Density after this cookbook

| Tab | Before (bytes) | Owns after CB13 |
|---|---|---|
| activity | 19,567 | conversations + callbacks |
| billing | 10,108 -> ~8,000 | amount due, invoices (paged), payments, prepaid pointer |
| requests | 10,219 | tickets |
| security | 9,745 | sessions, password, revoke-all |
| profile | 7,415 | identity, contact, addresses, locale |
| **services** | **4,699 -> ~9,500** | 3 tiles, lines, all balances, top-ups |
| assistant | 10,636 | live call |
| preferences | 4,367 | display settings |
| help | 2,781 -> ~3,400 | 5 deep links + 2 exits |
| about | 3,218 | static |

The two thinnest data tabs are no longer thin, and no data appears in two places. Still open from CB10 and deliberately deferred to keep this diff reviewable: notifications have no home tab (only the topbar reads them), and the Activity/Requests spatial budget is unchanged. Say the word and that becomes CB15.

---

## 13.6 Acceptance checks

| # | Check | Action | Pass condition |
|---|---|---|---|
| 1 | Prepaid credit visible | sign in as Yousra (prepaid), open /services | main credit in TND in the first tile |
| 2 | All types listed | same | main, data, voice, sms as returned - none filtered |
| 3 | Unknown type survives | temporarily insert a roaming balance row | renders last, no crash |
| 4 | Top-ups visible | same account | list with amount, bonus, channel, timestamp |
| 5 | Money vs quantity | inspect the credit tile and a data card | credit uses TND formatting; data uses GB/MB |
| 6 | No page swap | cold /services | four sections skeleton in place; total height stable |
| 7 | Failure is contained | fail only /me/balance | plan section renders; balance and top-up sections show inline errors |
| 8 | Profile failure contained | fail only /me/profile | balances and top-ups still render |
| 9 | No duplication | open /billing | no balance cards, no recharge list, one prepaid pointer |
| 10 | Pointer only when relevant | postpaid-only account (Amine) | pointer absent |
| 11 | Pointer works | prepaid account, click it | lands on /services |
| 12 | Help exits work | /help | both buttons navigate; action text legible without hover |
| 13 | No dead copy | `git grep -n "balanceTypes\|rechargeChannels" Frontend/customer_portal/src` | zero hits |
| 14 | Empty states name a step | force each empty list | every one has a title, a body and a next step |
| 15 | Responsive | 1440 / 1024 / 390 | tiles 3 -> 3 -> 1 columns; no cell under 44px tall; no horizontal scroll |
| 16 | Identity preserved | `git diff version_94..version_95 -- Frontend/customer_portal/src/styles.css` | empty |
| 17 | Orb untouched | `git diff version_94..version_95 -- Frontend/customer_portal/src/components/orb` | empty |
| 18 | Gates green | typecheck, lint, test, build | all pass |

### Rollback

| Change | Revert | Consequence |
|---|---|---|
| 13.1 Services | restore the version_94 file | prepaid credit hidden again |
| 13.2 Billing | restore both blocks | duplication returns; harmless but inconsistent |
| 13.3 Help | restore the card | Help is a dead end again |
| 13.4 copy | additive except the two deleted dead keys | check the grep before reverting |

Row 2 - the lines themselves:

```tsx
      <DataSection
        label={copy.services.plan}
        state={{
          isPending: profileQuery.isPending,
          isFetching: profileQuery.isFetching,
          isPlaceholderData: profileQuery.isPlaceholderData,
          error: profileQuery.error,
        }}
        items={subscriptions}
        skeletonRows={2}
        empty={{
          title: copy.services.subscriptionsEmpty.title,
          body: copy.services.subscriptionsEmpty.body,
        }}
        onRetry={() => void profileQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((sub) => (
              <Card key={sub.subscription_id}>
                <div className="flex items-start justify-between gap-sp-5">
                  <div className="min-w-0">
                    <div className="t-metric-l truncate text-ink-1">{sub.plan}</div>
                    <div className="t-mono-s mt-sp-4 text-ink-5">{sub.msisdn}</div>
                  </div>
                  {sub.status ? <StatusChip tone="solid">{sub.status}</StatusChip> : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </DataSection>
```

Keep the existing null-coalescing fallbacks the file already uses on plan and msisdn.

Row 3 - every balance type, not just data:

```tsx
      <DataSection<BalanceItem>
        label={copy.services.balances}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={balances}
        skeletonRows={3}
        empty={{
          title: copy.services.balancesEmpty.title,
          body: copy.services.balancesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2">
            {items.map((b, i) => (
              <div
                key={b.msisdn + b.balance_type + i}
                className="rounded-r-3 border border-stroke-subtle p-sp-6"
              >
                <div className="flex items-center justify-between gap-sp-5">
                  <span className="t-micro-2 text-ink-5">
                    {copy.labels.balanceType[b.balance_type]}
                  </span>
                  <StatusChip tone={b.status === "active" ? "outline" : "muted"}>
                    {b.status}
                  </StatusChip>
                </div>
                <div className="t-metric-l mt-sp-5 text-ink-1">{balanceValue(b)}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {b.msisdn}
                  {b.expires_on ? copy.services.expires(date(b.expires_on)) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </DataSection>
```

Row 4 - where the credit came from:

```tsx
      <DataSection<RechargeItem>
        label={copy.services.recharges}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={recharges}
        skeletonRows={3}
        empty={{
          title: copy.services.rechargesEmpty.title,
          body: copy.services.rechargesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <ul className="divide-y divide-stroke-subtle">
            {items.map((r, i) => (
              <li
                key={r.msisdn + r.created_at + i}
                className="flex items-center justify-between gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <div className="t-body-strong text-ink-1">
                    {money(r.amount)}
                    {r.bonus_amount ? (
                      <span className="t-caption text-ink-4">
                        {copy.billing.bonus(money(r.bonus_amount))}
                      </span>
                    ) : null}
                  </div>
                  <div className="t-caption mt-sp-1 truncate text-ink-5">
                    {r.msisdn}
                    {copy.labels.rechargeChannel[r.channel]}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="t-ui text-ink-3">{r.status}</div>
                  <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(r.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataSection>
    </div>
  );
}
```

Where two values share a line, reuse the same separator glyph and null fallbacks the Billing rows already use, so the moved sections read identically to the ones they replace.

Four things to notice, because they are the rules the rest of the portal should follow:

1. **No early return.** The page shape is fixed at first paint; sections fill in.
2. **No type filter.** An unknown balance type sorts last instead of disappearing.
3. **main is money, everything else is a quantity.** Rendering 90.30 TND through quantity() reads as a bundle; money() reads as credit.
4. **Two queries, four sections, four independent failure domains.**

---

## 13.2 Billing gives up balances and recharges

With Services owning them, delete from billing.tsx:

- the hasBalances block labelled copy.billing.balances
- the hasBalances block labelled copy.billing.recharges
- the now-unused quantity and dateTime imports, EmptyState if nothing else uses it, and copy.billing.balances / recharges / noRecharges if nothing else references them

Keep balanceQuery only to decide whether this customer has a prepaid side, and replace both blocks with one pointer so a hybrid customer is never stranded:

```tsx
      {hasBalances && (
        <PageSection>
          <Card className="flex items-center justify-between gap-sp-6">
            <p className="t-caption max-w-md text-ink-4">{copy.billing.prepaidPointer}</p>
            <Link
              to="/services"
              className="focus-ring t-ui shrink-0 rounded-r-2 px-sp-5 py-sp-3 text-ink-2 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
            >
              {copy.billing.prepaidPointerAction}
            </Link>
          </Card>
        </PageSection>
      )}
```

Add the Link import from @tanstack/react-router. Combined with CB12 section 12.3, Billing is now exactly: amount due, invoices with pagination, payments, and one line acknowledging prepaid.

---

## 13.3 Help must have an exit

help.tsx closes with a still-stuck card containing text and no action, while importing Button and never using it. The page whose only job is to route a stuck customer routes them nowhere. Replace the closing card body with two real exits:

```tsx
        <div className="flex shrink-0 gap-sp-4">
          <Link to="/assistant">
            <Button>{copy.help.talkToAssistant}</Button>
          </Link>
          <Link to="/requests">
            <Button variant="secondary">{copy.help.openRequest}</Button>
          </Link>
        </div>
```

The action line inside each topic card is also invisible until hover, which hides it from touch users entirely. Make it always legible and let hover carry only the emphasis:

```tsx
                  <span className="t-caption mt-sp-2 block text-ink-5 transition-colors group-hover:text-ink-3">
                    {t.action}
                  </span>
```

---

## 13.4 Copy keys

Add to lib/copy.ts under services, and delete the dead keys the version_94 patch introduced (services.balanceTypes, services.rechargeChannels). copy.labels.balanceType and copy.labels.rechargeChannel are the real homes and are already used by the components.

```ts
  services: {
    // existing keys stay
    tiles: {
      credit: "Credit",
      lines: "Active lines",
      linesHint: (total: number) => "of " + total + " total",
      plan: "Plan",
    },
    expires: (on: string) => "expires " + on,
    recharges: "Top-ups",
    balancesEmpty: {
      title: "No balances yet",
      body: "Balances appear here once your line is active. If you expect credit, ask the assistant to check the line.",
    },
    rechargesEmpty: {
      title: "No top-ups yet",
      body: "Top-ups you make by app, web, USSD, scratch card or at an agent appear here with any bonus credit.",
    },
    subscriptionsEmpty: {
      title: "No lines on this account",
      body: "If you have a line that is missing here, open a request and we will connect it to your account.",
    },
  },
```

under billing:

```ts
    prepaidPointer: "Your prepaid credit, bundles and top-ups live in Services.",
    prepaidPointerAction: "Open Services",
```

under help:

```ts
    talkToAssistant: "Talk to the assistant",
    openRequest: "Open a request",
```

and under common, if it is not already there, a notApplicable key using the same em-dash glyph the rest of copy.ts already uses.

Use template literals in place of the string concatenation above if that matches the existing style in copy.ts.

Every empty state names a next step. "No data" is not an empty state; it is an unanswered question.

---

## 13.5 Density after this cookbook

| Tab | Before (bytes) | Owns after CB13 |
|---|---|---|
| activity | 19,567 | conversations + callbacks |
| billing | 10,108 -> ~8,000 | amount due, invoices (paged), payments, prepaid pointer |
| requests | 10,219 | tickets |
| security | 9,745 | sessions, password, revoke-all |
| profile | 7,415 | identity, contact, addresses, locale |
| **services** | **4,699 -> ~9,500** | 3 tiles, lines, all balances, top-ups |
| assistant | 10,636 | live call |
| preferences | 4,367 | display settings |
| help | 2,781 -> ~3,400 | 5 deep links + 2 exits |
| about | 3,218 | static |

The two thinnest data tabs are no longer thin, and no data appears in two places. Deliberately deferred to keep this diff reviewable: notifications still have no home tab (only the topbar reads them), and the Activity/Requests spatial budget is unchanged. Both become CB15 on request.

---

## 13.6 Acceptance checks

| # | Check | Action | Pass condition |
|---|---|---|---|
| 1 | Prepaid credit visible | sign in as Yousra (prepaid), open /services | main credit in TND in the first tile |
| 2 | All types listed | same | main, data, voice, sms as returned - none filtered |
| 3 | Unknown type survives | temporarily insert a roaming balance row | renders last, no crash |
| 4 | Top-ups visible | same account | list with amount, bonus, channel, timestamp |
| 5 | Money vs quantity | inspect the credit tile and a data card | credit uses TND formatting; data uses GB/MB |
| 6 | No page swap | cold /services | four sections skeleton in place; total height stable |
| 7 | Failure is contained | fail only /me/balance | plan section renders; balance and top-up sections show inline errors |
| 8 | Profile failure contained | fail only /me/profile | balances and top-ups still render |
| 9 | No duplication | open /billing | no balance cards, no recharge list, one prepaid pointer |
| 10 | Pointer only when relevant | postpaid-only account (Amine) | pointer absent |
| 11 | Pointer works | prepaid account, click it | lands on /services |
| 12 | Help exits work | /help | both buttons navigate; action text legible without hover |
| 13 | No dead copy | grep for balanceTypes and rechargeChannels under Frontend/customer_portal/src | zero hits |
| 14 | Empty states name a step | force each empty list | every one has a title, a body and a next step |
| 15 | Responsive | 1440 / 1024 / 390 | tiles 3 -> 3 -> 1 columns; no cell under 44px tall; no horizontal scroll |
| 16 | Identity preserved | git diff version_94..version_95 on styles.css | empty |
| 17 | Orb untouched | git diff version_94..version_95 on components/orb | empty |
| 18 | Gates green | typecheck, lint, test, build | all pass |

### Rollback

| Change | Revert | Consequence |
|---|---|---|
| 13.1 Services | restore the version_94 file | prepaid credit hidden again |
| 13.2 Billing | restore both blocks | duplication returns; harmless but inconsistent |
| 13.3 Help | restore the card | Help is a dead end again |
| 13.4 copy | additive except the two deleted dead keys | check the grep before reverting |
