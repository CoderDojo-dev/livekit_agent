# Cookbook 10 - Tab organisation, spatial budget and visibility

**Target branch:** version_94 (cut from version_93 @ 192c969c35679cdf76f6145e4f0e1776a9abdf5c)
**Backend touched:** none (one optional additive endpoint in the appendix, behind your decision)
**Design tokens changed:** none. **Orb renderer touched:** none. **New npm packages:** none.
**Apply after CB9** - Services depends on the data CB9 exposes.

---

## 10.1 The problem this cookbook solves

The original complaint was crammed, overlapping content. CB4 fixed the mechanics: spacing tokens, `PageSection`, section-scoped states, pagination, animated tabs. The imbalance that remains is not styling - it is **content density per tab**. Measured on version_93:

| Tab | Route size | Density |
|---|---|---|
| activity | 19,567 B | dense |
| assistant | 10,636 B | dense |
| requests | 10,219 B | dense |
| billing | 10,108 B | dense |
| security | 9,745 B | dense |
| profile | 7,415 B | adequate |
| services | 4,699 B | **thin** |
| preferences | 4,367 B | adequate but partly untruthful |
| about | 3,218 B | static |
| help | 2,781 B | **static, non-interactive** |

Seven dense pages next to three sparse ones is the same imbalance as before, inverted. A customer who lands on Help or Services concludes the portal is unfinished - and on those two pages they are right.

### The three rules everything below follows

1. **Every tab earns its slot.** A tab must answer a question the customer actually arrives with, using data that exists. If it cannot, it merges into another tab. No tab exists to fill the rail.
2. **Vertical rhythm over horizontal cramming.** Two to three columns maximum at desktop width, one at mobile. Whitespace is the design, not wasted space. Never solve density by shrinking type or tightening the spacing tokens.
3. **Never show a number without its meaning, and never show a schema word.** Every value carries a label and a unit; every enum passes through `copy.ts`. This is already enforced by the guard script - it must stay enforced.

---

## 10.2 Spatial budget per tab

One pattern, applied everywhere, so no page invents its own:

```
row 1   up to 3 MetricTile - the answers to the tab's headline question
row 2   the primary list or the primary form, full width, paged
row 3   secondary context, at most 2 columns
```

| Tab | Row 1 (max 3 tiles) | Row 2 (primary) | Row 3 (secondary) |
|---|---|---|---|
| **services** | Credit / Data remaining / Plan | Balances grouped by type | Recent top-ups (CB9 9.7) |
| **billing** | Outstanding / Next due date / Account | Invoices, paged | Recent payments |
| **activity** | Calls this month / Last call / Avg duration | Conversations, paged | Notifications, paged |
| **requests** | Open / In progress / Resolved | Tickets, paged, filtered | Scheduled callbacks |
| **assistant** | none - the orb owns row 1 | Orb + transcript + tool timeline | Post-call summary |
| **security** | Password age / Active sessions / Last sign-in | Active sessions | Password change + revoke-all |
| **profile** | none | Identity + contact detail | Subscriptions |
| **preferences** | none | Display settings | Language honesty note (10.5) |
| **about** | none | What the assistant can and cannot do | Version + contact |
| **help** | none | Deep-linked topics (10.6) | Contact routes |

### Column rules, once, in the shell

Apply as the shared page grid; do not re-declare per route:

```tsx
// Two columns is the ceiling for reading comfort at 1440px with the rail open.
// Three is only ever used for MetricTile rows, which are glanceable, not read.
<div className="grid grid-cols-1 gap-sp-6 lg:grid-cols-2">
<div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2 lg:grid-cols-3">  {/* tiles only */}
```

The existing breakpoint contract from CB4 is unchanged: the rail collapses to the tabbar below `lg`, and every table becomes a stacked card list below `md`. No table may scroll horizontally on a phone - that was the original overlap complaint and it must never return.

---

## 10.3 The two structural changes

**Sessions appear on both `security.tsx` and `profile.tsx`.** Verified by size and content: both render a session grid. Duplicated data in two tabs is exactly the disorganisation to remove. Decision: **sessions live only on Security** - that is where a customer goes to end a session. Profile keeps identity, contact and subscriptions. Remove the session grid from `profile.tsx` and add a single link:

```tsx
            <Link to="/security" className="t-caption text-ink-3 hover:text-ink-1 focus-ring">
              {copy.profile.sessionsMoved}
            </Link>
```

```ts
    sessionsMoved: "Manage where you are signed in ->",
```

**Notifications have no home.** `fetchNotifications` exists and Activity is the only plausible host. Put them in Activity row 3 as a second `AnimatedTabs` group (Calls / Messages) - and this is precisely why CB8 8.6.1 parameterised `layoutId`. Pass an explicit `groupId`:

```tsx
            <AnimatedTabs groupId="activity-secondary" tabs={...} value={...} onChange={...} />
```

---

## 10.4 Services, rebuilt on the CB4 contract

Two problems beyond thinness, both verified in `services.tsx`:

```tsx
  if (profileQuery.isPending || balanceQuery.isPending) {
    return ( ...full page skeleton... );
  }
  if (profileQuery.isError) {
    return ( <Card><ErrorState .../></Card> );
  }
```

A full-page skeleton swap causes a layout jump the section-scoped skeletons were built to avoid, and a whole-page error replacement contradicts CB4's rule that an error never replaces the page - a failing balance must not hide a perfectly good plan card.

### Full replacement for the component body

```tsx
function ServicesPage() {
  const { customerId } = usePortalSession();
  const profileQuery = useQuery({
    queryKey: qk.profileDetail(customerId),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(customerId),
    queryFn: () => fetchBalance(),
    staleTime: 30_000,
  });

  const balances = balanceQuery.data?.balances ?? [];
  const recharges = balanceQuery.data?.recharges ?? [];
  const groups = groupBalances(balances);
  const credit = balances.find((b) => b.balance_type === "main");
  const data = balances.find((b) => b.balance_type === "data");

  // No early return. Each section owns its own pending and error state, so a
  // failing balance request can never hide the plan, and a slow profile can
  // never blank the page.
  return (
    <div className="flex flex-col gap-sp-8">
      <div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile
          label={copy.services.tiles.credit}
          value={credit ? balanceValue(credit) : "-"}
          pending={balanceQuery.isPending}
        />
        <MetricTile
          label={copy.services.tiles.data}
          value={data ? balanceValue(data) : "-"}
          pending={balanceQuery.isPending}
        />
        <MetricTile
          label={copy.services.tiles.plan}
          value={profileQuery.data?.plan_name ?? "-"}
          pending={profileQuery.isPending}
        />
      </div>

      <DataSection
        label={copy.services.balances}
        state={balanceQuery}
        empty={copy.services.balancesEmpty}
        onRetry={() => void balanceQuery.refetch()}
      >
        <div className="flex flex-col gap-sp-6">
          {groups.map((group) => (
            <section key={group.type}>
              <h3 className="t-label text-ink-4">{group.label}</h3>
              <ul className="mt-sp-3 grid grid-cols-1 gap-sp-3 lg:grid-cols-2">
                {group.items.map((item, i) => (
                  <li key={`${item.msisdn ?? "na"}-${i}`} className="portal-section flex items-baseline justify-between gap-sp-4">
                    <div className="min-w-0">
                      <p className="t-body-l text-ink-1">{balanceValue(item)}</p>
                      {item.msisdn ? <p className="t-caption text-ink-4">{msisdn(item.msisdn)}</p> : null}
                    </div>
                    <div className="text-right">
                      <StatusPill status={item.status} />
                      {item.expires_on ? (
                        <p className="t-caption text-ink-4">{copy.services.expires} {date(item.expires_on)}</p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </DataSection>

      <DataSection
        label={copy.services.subscriptions}
        state={profileQuery}
        empty={copy.services.subscriptionsEmpty}
        onRetry={() => void profileQuery.refetch()}
      >
        {/* existing subscription cards, unchanged */}
      </DataSection>

      {/* Recent top-ups: CB9 9.7 */}
    </div>
  );
}
```

New copy keys:

```ts
    tiles: { credit: "Credit", data: "Data remaining", plan: "Your plan" },
    balancesEmpty: "No balances on your line yet.",
    subscriptionsEmpty: "No active subscriptions on your account.",
    expires: "Expires",
```

`MetricTile` needs a `pending` prop if it does not already have one - a tile that renders `-` while loading is indistinguishable from a tile that means zero:

```tsx
export function MetricTile({ label, value, pending }: { label: string; value: string; pending?: boolean }) {
  return (
    <div className="portal-section">
      <p className="t-label text-ink-4">{label}</p>
      {pending ? <SkeletonMetric /> : <p className="t-display text-ink-1">{value}</p>}
    </div>
  );
}
```

---

## 10.5 Preferences - remove the promise the portal cannot keep

`lib/preferences.ts` is `localStorage`-only and there is no preferences endpoint on the backend - I verified the business-api module listing. Density, motion and theme are legitimately browser-local. **Language is not**: the assistant's language comes from the customer record the agent reads, so a portal switch reading "English" while the assistant answers in French is a lie the customer will notice inside one call.

**Default (implement this): label it honestly.** Zero backend work, zero risk.

```tsx
        <PageSection label={copy.preferences.display}>
          {/* density, motion, theme - unchanged, they are genuinely local */}
          <p className="t-caption text-ink-4">{copy.preferences.scopeNote}</p>
        </PageSection>
```

```ts
    display: "Display",
    displayLanguage: "Portal display language",
    scopeNote:
      "These settings apply to this browser only. The language your assistant speaks follows your account and is set when you speak to us.",
```

Rename the control from "Language" to `copy.preferences.displayLanguage`. That single word is the difference between an honest setting and a broken one. The alternative - a real `PATCH /api/v1/me/preferences` - is fully specified in the appendix and is **your call**, not mine to assume.

Also respect the motion preference the page offers. If `prefers-reduced-motion` or the stored motion preference is off, the CB4 animations must degrade to opacity-only:

```tsx
// A motion toggle that animates anyway is the same class of bug as a language
// toggle that changes nothing.
const reduce = useReducedMotion() || preferences.motion === "off";
const T = reduce ? { duration: 0 } : T_BASE;
```

---

## 10.6 Help - make it lead somewhere or fold it away

Verified: `help.tsx` renders `copy.help.topics` as cards with icons. The cards are not links, there are no destinations, and there is no search. It is the only tab with zero data and zero interaction.

**Implement this: give every topic a destination inside the portal.** No content backend, no new endpoint, ~20 lines.

```tsx
// A help topic that does not lead anywhere is decoration. Every topic resolves
// to the tab that actually answers it, or to the assistant, which can answer
// anything. No topic links outside the portal.
const HELP_TOPICS = [
  { id: "plan",     icon: Compass,     to: "/services" },
  { id: "bill",     icon: ReceiptText, to: "/billing" },
  { id: "request",  icon: LifeBuoy,    to: "/requests" },
  { id: "security", icon: Shield,      to: "/security" },
  { id: "assistant",icon: AudioLines,  to: "/assistant" },
] as const;
```

```tsx
      <div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2">
        {HELP_TOPICS.map((topic) => {
          const Icon = topic.icon;
          const t = copy.help.topics[topic.id];
          return (
            <Link key={topic.id} to={topic.to} className="portal-section focus-ring group flex items-start gap-sp-4">
              <Icon className="size-5 shrink-0 text-ink-3" aria-hidden />
              <div className="min-w-0">
                <p className="t-body-l text-ink-1">{t.title}</p>
                <p className="t-caption text-ink-4">{t.body}</p>
                <span className="t-caption text-ink-3 opacity-0 transition-opacity group-hover:opacity-100">
                  {t.action}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
```

Each topic in `copy.ts` gains an `action` line naming the destination ("See your balances", "Open your invoices", ...). Close the page with the one thing a help page must always offer - a way to reach a human, which the portal genuinely has:

```tsx
        <PageSection label={copy.help.stillStuck}>
          <Link to="/assistant" className="...">{copy.help.talkToAssistant}</Link>
          <Link to="/requests" className="...">{copy.help.openRequest}</Link>
        </PageSection>
```

Do not add a help search box: there is no help corpus to search, and a search that returns nothing is worse than no search. If you would rather have nine tabs than a linking Help page, merging Help into About is equally honest - specified but not implemented here.

---

## 10.7 Empty states must say what to do next

Audit every `empty` string. An empty state has three jobs: confirm nothing is wrong, explain why it is empty, offer the next step. Most current strings do only the first.

| Where | Replace with |
|---|---|
| conversations | "No calls yet. Start one from the Assistant tab and it will appear here." |
| requests | "No requests open. If something is wrong, ask the assistant and it can raise one for you." |
| invoices | "No invoices yet. Postpaid invoices appear here after your first billing cycle." |
| notifications | "No messages from us recently. Alerts about your line appear here." |
| callbacks | "No callbacks scheduled. The assistant can arrange one at a time that suits you." |
| balances | "No balances on your line yet." |
| sessions | "Only this device is signed in." |

An empty state must never render an error tone, and a filtered empty result must be distinguishable from a genuinely empty dataset:

```tsx
  empty={status ? copy.requests.emptyFiltered : copy.requests.empty}
```

---

## 10.8 Visibility and polish checklist

All verifiable by inspection, no new tooling:

1. **Contrast.** Every `t-caption text-ink-4` on `surface-1` or darker must clear 4.5:1. `--ink-4` on `--surface-0` is the pairing to check first; use `--ink-3` where it fails. Do not change token values.
2. **Focus.** Every interactive element carries `.focus-ring`. Tab through all ten tabs with the rail open and collapsed; no element may be reachable without a visible ring, and none may be unreachable.
3. **Truncation.** Every value that can be long - plan names, ticket subjects, template codes - needs `truncate` plus a `title`. Truncation without a tooltip hides data.
4. **No layout shift.** A skeleton must occupy the same height as the row it replaces. Load each tab on a throttled connection and watch for a jump when data lands.
5. **Sticky overlap.** With the topbar sticky and the callbar at `--z-callbar: 40`, confirm no section header hides under either at any scroll position. This was the original overlap complaint.
6. **One h1 per page.** The page title in the topbar is the `h1`; section labels are `h2`, groups inside them `h3`. Verify with the accessibility tree, not by eye.
7. **Tabbar reachability.** Below `lg`, all ten destinations must be reachable in the tabbar - scrollable is fine, silently cut off is not.
8. **Pagination at the bottom.** Page indicators sit below the list, always, per the original requirement. Never above, never both.

---

## 10.9 Acceptance checks

| # | Check | Pass condition |
|---|---|---|
| 1 | Services is no longer thin | 3 tiles, grouped balances, subscriptions, top-ups; nothing overlaps at 1440/1024/390 px |
| 2 | No early return in services.tsx | `grep -n "if (.*isPending) {" src/routes/_portal/services.tsx` returns nothing |
| 3 | Partial failure degrades | stop business-api mid-session: plan card stays, balances show an inline error |
| 4 | Sessions appear once | `grep -Rn "sessions" src/routes/_portal/profile.tsx` finds only the link |
| 5 | Notifications have a home | Activity shows a Messages group with its own paging |
| 6 | Two tab groups coexist | each animates its own underline (CB8 8.6.1) |
| 7 | Help leads somewhere | every topic card navigates; keyboard-reachable |
| 8 | Language is honest | the control reads "Portal display language" and the scope note is visible |
| 9 | Motion preference honoured | with motion off, no transform animations run |
| 10 | Empty states actionable | every empty string names a next step |
| 11 | Filtered vs empty | distinct strings |
| 12 | No schema words | `grep -REn "balance_type\|template_code\|scratch_card\|in_progress" src/routes` finds none outside type positions |
| 13 | No horizontal scroll | at 390 px width, no page scrolls sideways |
| 14 | Tokens untouched | `git diff version_93..version_94 -- Frontend/customer_portal/src/styles.css` is empty |
| 15 | Orb untouched | `git diff version_93..version_94 -- Frontend/customer_portal/src/components/orb` is empty |

---

## Appendix - optional: make preferences real (`PATCH /api/v1/me/preferences`)

Only if you choose option (b) in 10.5. Additive, no migration - `customers.preferred_language` already exists.

New function in `me_reads.py` (the only write it would contain, so name it explicitly):

```python
async def update_preferred_language(
    session: AsyncSession, customer_id: UUID, language: str
) -> dict[str, Any]:
    """Set the language the assistant speaks. The only write in this module.

    Whitelisted values only: this column drives agent behaviour, so an
    arbitrary string from a browser must never reach it.
    """
    if language not in _ALLOWED_LANGUAGES:
        raise ValueError("unsupported_language")
    await session.execute(
        update(Customer)
        .where(Customer.id == customer_id)
        .values(preferred_language=language)
    )
    await session.commit()
    return {"preferred_language": language}


_ALLOWED_LANGUAGES = ("fr", "ar", "en")
```

Route:

```python
@app.patch("/api/v1/me/preferences")
async def me_preferences(
    body: PreferencesUpdate,
    principal: Annotated[Principal, Depends(require_client)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        return await me_reads.update_preferred_language(
            session, _client_customer_id(principal), body.preferred_language
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="unsupported_language") from None
```

Constraints if you take this path: whitelist enforced server-side (never trust the select), no other column writable, the customer id still comes from the token and never from the body, and the French-first corpus decision stands - offering `ar`/`en` in the portal while the model is French-only would reintroduce exactly the dishonesty this section removes. Ship option (a) unless you also intend to change the model.
