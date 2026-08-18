# Review of version_94 - what landed, what did not, what is now wrong

**Reviewed ref:** `version_94` = commit/tree `48004d601f6eec165e26fc3d956f573d7b4636ec`
**Method:** every claim below comes from reading the file on that ref. Where the results document and the branch disagree, the branch wins and I say so.
**Next target branch:** `version_95`

---

## 1. Verified landed, correct, no follow-up needed

| Item | Evidence on the branch |
|---|---|
| **CB8.1 token gate (the P0)** | `apps/token-service/.../main.py`: `INTERNAL_API_KEY`, `INTERNAL_KEY_HEADER`, `token(req, request: Request)`, `trusted = bool(INTERNAL_API_KEY) and header == key`, warning on ignored MSISDN, `caller_msisdn = (req.caller_msisdn if trusted else None) or PILOT_MSISDN`, `allow_headers=["Content-Type", INTERNAL_KEY_HEADER]`. Implemented exactly as specified, and you proved it live: untrusted call returned `+21620155320` instead of the supplied `+21690000000`. **The impersonation path is closed.** |
| **CB8.4 turn ordering** | `me_reads.conversation_detail`: `.order_by(Turn.turn_index.asc(), Turn.created_at.asc())` |
| **CB8.6.1 AnimatedTabs** | `data.tsx`: `useId()`, `groupId?`, `underlineId`, `layoutId={underlineId}` |
| **CB8.6.2 DataSection dim** | `animate={{ opacity: state.isPlaceholderData ? 0.55 : 1 }}`; `isPlaceholderData?` added to the state type |
| **CB8.6.3 Panel modality** | opener captured, `document.body.style.overflow = "hidden"`, Tab cycle over the sheet's tabbables, Escape, `opener?.focus?.()` on cleanup, `sheetRef` attached to `motion.aside` |
| **CB8.6.4 TopProgress** | `h-0.5` on both wrapper and bar |
| **CB9 billing() aggregate** | `_EXCLUDED_OUTSTANDING = ("paid", "void")` module constant; `func.count(Invoice.id)` + `func.coalesce(func.sum(case(...)))` over all `account_ids`; invoice query `.offset(start).limit(size)`; envelope `invoices: {total, limit, offset, items}` with `total_outstanding` deliberately outside it. This is the hardest item in CB9 and it is right. |
| **CB9 billing frontend** | `billing.tsx`: `PAGE_SIZE = 20`, `qk.billing(cid, PAGE_SIZE, page*PAGE_SIZE)`, `placeholderData: keepPreviousData`, `billing?.invoices.items`, `<Pagination total={invoiceTotal} .../>` under the list inside the same `DataSection` |
| **CB10 Help deep links** | `help.tsx`: `HELP_TOPICS` with `to:` targets, rendered as `<Link>` with icon, title, body and a hover-revealed `action` |
| **Discipline** | `styles.css` and `components/orb/` untouched; no new dependency; no migration; `repositories.py` not touched |

Also worth stating plainly: `billing.tsx` now renders **all** balance types and the recharge list. The data depth CB9 asked for exists - it just landed on the wrong tab (see §3).

---

## 2. The results document contains one false claim

> "`notifications()` and `callbacks()` now return `{total, limit, offset, items}` ... Windowed: `.offset(start).limit(size)` ✓"

The branch does not do this. Both functions resolve the window and then never apply the offset:

```python
    size, start = _page(limit, offset)
    total = session.scalar(select(func.count(Notification.id)).where(...))
    rows = session.execute(
        select(...)
        .where(Notification.customer_id == customer_id)
        .order_by(Notification.created_at.desc())
        .limit(size)          # <-- no .offset(start)
    ).all()
    return {"total": ..., "limit": size, "offset": start, "items": items}
```

`callbacks()` is identical. So the envelope **reports** an offset the query never applied: every page returns the newest `size` rows while claiming to be page 2, 3, 4. This is worse than the version_93 behaviour it replaced, because version_93 was honestly unpaged - this one lies in a machine-readable field, and `Pagination` will happily render page numbers that all show the same rows.

Why the live check missed it: the test was "does the route accept `offset` without a 422", which it does. Accepting a parameter and honouring it are different assertions. CB12 1.1 fixes the code and CB14 3.2 adds the regression test that would have caught it.

No criticism of the runtime work - the token-gate proof in the same document is exactly the right kind of evidence, and it is why the P0 can be closed with confidence.

---

## 3. CB9 §9.7 and CB10 §10.4 were not applied

`services.tsx` on version_94 is the version_93 file plus the single CB8.3 line. Still present:

```tsx
function isDataBalance(balance: BalanceItem): boolean {
  return balance.balance_type === "data" && (balance.unit === "GB" || balance.unit === "MB");
}
...
  if (profileQuery.isPending || balanceQuery.isPending) { return ( ...full-page skeleton... ); }
  if (profileQuery.isError || !profileQuery.data) { return ( <Card><ErrorState /></Card> ); }
```

Consequences on the branch right now:

- **Services still hides prepaid credit.** `main`, `voice` and `sms` balances are fetched and filtered out. The tab named after the customer's services shows only data bundles.
- **Services still breaks the CB4 state contract** - full-page skeleton swap (layout jump) and whole-page error replacement (a failed profile hides a healthy balance list).
- **The copy keys added for it are dead.** The results document lists `services.balanceTypes`, `services.recharges`, `services.rechargeChannels` as added; `services.tsx` uses `copy.labels.balanceType` instead and never references the others. Dead keys, live confusion.
- **Balances and recharges are now rendered in two tabs with different completeness**: Billing shows every type plus top-ups, Services shows data only. Same data, two places, two answers. That is precisely the content-organisation problem to eliminate, and it needs an ownership decision (CB13 §2).

---

## 4. New defects introduced or newly visible in version_94

### 4.1 `nextDue` is computed from one page of invoices

`billing.tsx`:

```tsx
  const nextDue = useMemo(() => { const dues = invoices.filter(...).map(i => i.due_date)...sort(); return dues[0]; }, [invoices]);
...
          <MetricTile size="xl" label={copy.billing.amountDue}
            value={money(billing.total_outstanding, billing.currency_code)}
            hint={nextDue ? date(nextDue) : undefined} />
```

`total_outstanding` is account-wide and page-independent - CB9 went to real trouble to make it so. The `hint` sitting directly under it is derived from `invoices`, which is now **one page**. Page to invoice 21+ and the due date under an unchanging total changes. It is the same bug CB9 removed from the server, reintroduced two lines away from the value it contradicts. Fix in CB12 1.2 (account-wide `next_due_date`, additive).

### 4.2 `billing.tsx` keeps the whole-page skeleton and the whole-page error

```tsx
  if (billingQuery.isPending || balanceQuery.isPending) { return <full page skeleton>; }
  if (billingQuery.isError || !billing) { return <Card><ErrorState /></Card>; }
```

It correctly builds a `DataSection` for invoices - and then makes it unreachable while either query is pending, including the **balance** query, which the invoice list does not depend on. A slow prepaid balance blanks the entire billing page. Same defect class as Services.

### 4.3 `profile.tsx` is outside every convention the portal has

Four distinct problems in one file:

```tsx
  const query = useQuery({
    queryKey: ["me", "profile", "detail"],   // not qk.profileDetail(cid)
    queryFn: () => fetchProfileDetail(),      // no staleTime
  });
```

1. **The key is not customer-scoped.** `query-keys.ts` states the rule in its own docstring: "Every key carries the signed-in customer id so a different account can never see another account's cached rows." This key carries none, so sign out and sign in as another customer in the same tab and the cache can serve the previous customer's name, email, phone and address until it goes stale. It is also invisible to the post-call `["me", customerId]` invalidation.
2. **No `staleTime`**, unlike every other page (30_000).
3. **Hand-rolled pending and error states**: `<p>Loading your details…</p>` and a whole-page error card - no skeleton, guaranteed layout jump.
4. **Invented verification status** - the worst of the four:

```tsx
  action={me.email ? <StatusChip tone="outline">VERIFIED</StatusChip> : null}
  action={<StatusChip tone="dashed">UNVERIFIED</StatusChip>}
```

Email is labelled VERIFIED because a string exists, and phone is **always** labelled UNVERIFIED regardless of reality. Neither claim comes from data. Telling a customer their number is unverified when it is the MSISDN we bill is a support call we manufactured.

### 4.4 A VIP flag is rendered to the customer

```tsx
              {me.vip ? <StatusChip tone="solid" className="ml-auto">VIP</StatusChip> : null}
```

The portal's own rule bans internal supervision and segmentation signals from customer-facing reads, and `customer_vip` is on the forbidden-key grep list. The projection field is named `vip`, so the grep does not catch it and the guard passes. VIP tiering is internal commercial segmentation: showing it invites "why am I not VIP", and its absence is equally loaded. Remove from the UI, and from `/me/profile/detail` unless you consciously decide it is a customer-facing benefit.

### 4.5 Help ends in a dead end

`help.tsx` closes with a "still stuck" card containing an icon and two lines of text and **no action**. `Button` is imported and never used (this is likely the "1 fixable" lint warning in the results document). The one page whose entire purpose is to route a stuck customer somewhere routes them nowhere.

### 4.6 `MetricTile` still has no pending state

No `pending` prop, so during load a tile renders whatever the caller passes - usually `"—"` - which is indistinguishable from a real zero or a real empty. Every tile row in the portal has this ambiguity.

---

## 5. Still open from earlier cookbooks

| Item | Status |
|---|---|
| CB10 per-tab spatial budget (the ten-tab table) | not applied |
| CB10 §10.3 notifications need a home tab | not applied - notifications are consumed only by `portal-topbar.tsx` |
| CB10 §10.7 empty states that name a next step | not applied |
| CB10 §10.5 preferences honesty note | reported applied; not re-read on this ref |
| CB11 entirely - live call, orb states, tool events, auth paths, responsive sweep | **not run.** Your own document says so |
| `verify-portal.sh` | still never executed anywhere; the CI step exists and the first run is expected to fail |
| `repositories.py` / `models/__init__.py` ruff question | still unanswered; only a CI run settles it |

---

## 6. What version_95 should contain, in order

1. **`12-data-truth-fixes.md`** - the offset bug, account-wide `next_due_date`, `profile.tsx` brought inside the conventions, invented verification chips removed, VIP removed, `MetricTile pending`. These are correctness and honesty items; nothing here is cosmetic.
2. **`13-services-and-billing-boundary.md`** - decide which tab owns balances and recharges, rebuild Services on `DataSection`, delete the duplicate, remove the whole-page early returns from both, apply the spatial budget, give Help an exit.
3. **`14-runtime-proof-and-ci.md`** - the runtime proof that has never happened, plus the four regression tests that make this class of silent divergence impossible to ship again.

One decision is needed from you before CB13 can be applied as written; it is stated at the top of that file.

---

## 7. Honest status of the portal

Structurally it is in good shape: the security boundary is correct, the state machinery exists and is used, pagination is real on the one screen that has it, and the design identity is intact. Two things stand between it and "complete":

- **a small number of truth bugs** - a lying offset, a page-scoped due date, invented verification badges, a leaked VIP flag. Each is small; together they are the difference between a portal a customer trusts and one they call support about.
- **the absence of runtime proof.** Not one live call has been made against this code. Until CB14 §1 and §2 are green, "works with no problems" is an expectation, not a finding.
