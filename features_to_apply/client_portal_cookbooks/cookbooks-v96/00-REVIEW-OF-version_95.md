# Review of version_95

**Branch read:** `91f2b1a396eb4c6846f134f385d1ee54c0008f1a`
**Files read:** me_reads.py, services.tsx, billing.tsx, profile.tsx, help.tsx, data.tsx, copy.ts, query-keys.ts, verify-portal.sh, activity.tsx, security.tsx, requests.tsx, portal-topbar.tsx, tests/ directory listing.

---

## 1. Verified landed

| Item | Verified by |
|---|---|
| notifications() .offset(start) + id.asc() tiebreak | me_reads.py line ~320 |
| callbacks() .offset(start) + id.asc() tiebreak | me_reads.py line ~355 |
| billing() next_due_date via func.min(case(...)) | me_reads.py line ~240-260 |
| billing() envelope: total / limit / offset / items | me_reads.py |
| services.tsx full rebuild: BALANCE_ORDER, orderBalances, balanceValue | services.tsx |
| Three MetricTile tiles (credit / lines / plan) all with pending= | services.tsx |
| Four DataSection rows, no filter, no early return | services.tsx |
| billing.tsx: next_due_date from server, useMemo gone | billing.tsx |
| billing.tsx: both early returns deleted | billing.tsx |
| billing.tsx: no balance/recharge sections, prepaid pointer with Link | billing.tsx |
| postpaid = billing ? billing.accounts.length > 0 : true | billing.tsx |
| profile.tsx: qk.profileDetail(cid) + staleTime: 30_000 | profile.tsx |
| profile.tsx: skeleton nav + card on pending | profile.tsx |
| profile.tsx: ErrorState inline, no VERIFIED/UNVERIFIED chips, no VIP chip | profile.tsx |
| help.tsx: two real exits + always-legible action text | help.tsx |
| MetricTile pending prop + barHeight per size | data.tsx |
| pageWindow exported | data.tsx |
| copy.ts: all new keys, dead keys gone, common.notApplicable present | copy.ts |
| query-keys.ts: all keys customer-scoped | query-keys.ts |
| verify-portal.sh: check 13 present and correct | verify-portal.sh |
| Notifications now live in the Activity > Messages secondary tab with pagination | activity.tsx |
| security.tsx: password change + sessions + revoke-all working | security.tsx |
| requests.tsx: search + tabs + pagination + detail panel | requests.tsx |
| Build clean, typecheck 0 errors, lint 0 errors (1 pre-existing warning), 17/17 tests, 13/13 verify-portal checks | results doc |

All gaps from the version_94 review are closed. The CB10 deferred item (notifications with no home tab) is also resolved: activity.tsx gives them the Messages secondary tab.

---

## 2. One real bug found by reading the branch

### portal-topbar.tsx: unscoped profile query key

Line 35 (approximately):

```ts
  const profile = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });
```

Profile.tsx now uses `qk.profileDetail(cid)` = `["me", cid, "profile-detail"]`.

These are two different cache entries. Consequences:

1. **Wasted fetch.** Every page load makes two calls to `/me/profile/detail`: one for the topbar and one for the profile page. The RTK dedup only fires on identical keys.
2. **The topbar key survives logout sweeps.** On sign-out, the logout flow should call `queryClient.removeQueries({ queryKey: ["me", customerId] })` to evict every customer-scoped cache entry. The unscoped topbar key `["me", "profile", "detail"]` does not match that prefix; it stays warm.
3. **Cross-account name bleed after a same-tab account switch.** Yousra signs in, name caches under the unscoped key. Yousra signs out, scoped keys are swept, unscoped key survives. Amine signs in. The topbar renders Yousra's name until the unscoped staleTime expires (currently no staleTime = 0, so it refetches on focus, but not immediately on mount).

This is CB16, section 16.1. It is a one-line fix.

---

## 3. Test files not committed

The tests directory listing on version_95 does not contain `test_me_reads_paging.py` or `test_me_reads_isolation.py`. Both ran locally (27 passed) but were not committed. The 27 assertions that make the offset class of bug unshippable exist only in the container.

This is CB16, section 16.2.

---

## 4. Still-open items

| # | Item | Status |
|---|---|---|
| A | portal-topbar.tsx unscoped profile key | CB16 16.1 |
| B | test_me_reads_paging.py + test_me_reads_isolation.py not committed | CB16 16.2 |
| C | Browser-only checks from the results doc | User's browser |
| D | Live call (nine orb states, tool events, greeting the signed-in customer) | Needs mic + LiveKit |
| E | credentials test-client-403@example.tn / client-secret-test-55 in repo history | Rotate before sharing |
| F | 48 notifications with customer_id NULL (seed finding) | Carry; document or rebind |
| G | CI run result on version_95 still unknown | First push to version_95 triggers it |

Items C and D are verification, not code changes. Items E and F are operational hygiene. G resolves itself on push.

---

## 5. Portal completeness after CB16

Every tab is implemented and self-consistent. No data appears in two places. No early return blanks a page. No invented data reaches the screen. The VIP, VERIFIED/UNVERIFIED, and forbidden-key audits are all clean on the branch. The only remaining code change before "fully implemented" is the one-line topbar key fix and the two uncommitted test files.
