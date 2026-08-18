# Review of `version_93` — what landed, what is still wrong, what comes next

**Reviewed ref:** `CoderDojo-dev/livekit_agent` @ `version_93`, tree `192c969c35679cdf76f6145e4f0e1776a9abdf5c`
**Reviewed against:** the seven cookbooks delivered for `version_92`, and `patch-v93-client-portal-cookbooks-results.md`
**Method:** file-by-file read of the branch as committed. Nothing below is inferred from the results document; every claim names the file it came from. Where I could not execute something (no Docker, no DB, no `npm` in this environment), it is listed as *unverified* rather than asserted.

---

## 1. Verdict

The seven cookbooks did land, and they landed faithfully. This is not a partial application: the whole shape is there.

| Cookbook | Evidence on the branch | Status |
|---|---|---|
| CB1 audit/cleanup | `src/lib/fixtures/` is **absent** from `src/lib/`; no `SCRIPT`/demo modules remain in the tree listing | applied |
| CB2 auth foundation | `routes/logout.tsx` (1,310 B), `components/shell/account-menu.tsx` (4,439 B), `lib/api/auth.server.ts` (5,950 B), `lib/api/errors.ts`, `lib/use-portal-session.ts` | applied |
| CB3 customer data | `apps/business-api/src/business_api/me_reads.py` (19,207 B) + `lib/api/{account,activity,billing,notifications,requests}.server.ts` + `lib/format.ts` + `lib/query-keys.ts` | applied |
| CB4 UX/layout | `components/portal/data.tsx` (15,962 B) with `PageSection`, `Skeleton*`, `TopProgress`, `Pagination`, `DataSection`, `ErrorState`, `Panel`, `InteractiveRow`, `AnimatedTabs`, `TabPanel`, `MetricTile`; `components/shell/brand-mark.tsx` | applied |
| CB5 orb/realtime | `lib/api/voice.server.ts`, `lib/orb-state.ts`, `hooks/use-orb-level.ts`, `hooks/use-input-controls.ts`, `components/assistant/{voice-session,live-stream,agent-session-provider,start-audio-button,participant-name}.tsx`, rebuilt `routes/_portal/assistant.tsx` with `ssr: false` | applied |
| CB6 tool timeline | `lib/tool-events.ts` (5,697 B), `components/assistant/{tool-event-row,working-indicator}.tsx` | applied |
| CB7 polish/CI | 4 test files (`orb-state`, `tool-events`, `format`, `copy`), `package.json` scripts `typecheck`/`test`/`verify`, CI job `customer-portal-test` | applied |

**Both approval gates I raised were honoured and implemented correctly:**

1. LiveKit dependencies are present and, better than the cookbook, **pinned exact** — `"livekit-client": "2.21.0"`, `"@livekit/components-react": "2.9.23"` in `Frontend/customer_portal/package.json`. The deviation note explains why (`AgentSessionProvider`/`StartAudioButton` are not exported from 2.9.24/2.22.0). Pinning exact was the right call, and the two local ports (`agent-session-provider.tsx`, `start-audio-button.tsx`) are the correct compensating move.
2. The token-service field landed as specified: `apps/token-service/src/token_service/main.py` now has `caller_msisdn: str | None = None` on `TokenRequest` and `caller_msisdn = req.caller_msisdn or PILOT_MSISDN`. Default behaviour is byte-for-byte preserved for `apps/client-widget`, which sends no such field.

The orb was not touched: `components/orb/` still holds `orb.tsx`, `orb-renderer.ts`, `orb-plinth.tsx`, and `assistant.tsx` consumes `<Orb state={...} level={...} size={...} />` without editing the renderer. The design identity is intact — `styles.css` is still the token file (10,052 B) and every new component uses `--sp-*`, `--r-*`, `t-*`, `text-ink-*`, `bg-surface-*` classes rather than raw hex or Tailwind defaults.

So: the portal is no longer a template. It is a real, authenticated, server-backed application.

**But it is not yet "perfect and fully implemented".** I found 14 concrete defects. One is a security escalation that the `caller_msisdn` change introduced. Four are correctness bugs that a customer will hit. The rest are consistency and depth gaps against the very rules CB4 set. They are all fixable in one more batch, and none requires rewriting anything that landed.

---

## 2. The one finding that matters most: `/token` now trusts a client-supplied MSISDN

**Severity: P0. This is a regression in trust boundary, introduced by Option A.**

Verified in `apps/token-service/src/token_service/main.py` on `version_93`:

- `POST /token` still has **no authentication** — no dependency, no header check, no service key. Same as `version_92`.
- CORS still allows `CORS_ORIGINS` (default `http://localhost:5173`).
- `TokenRequest` accepts `room`, `identity`, `name` — and now **`caller_msisdn`**.
- The route sets the room attribute from it: `caller_msisdn = req.caller_msisdn or PILOT_MSISDN`, then `.with_attributes({CALLER_MSISDN_ATTRIBUTE: caller_msisdn})`.
- `CALLER_MSISDN_ATTRIBUTE = "telecom.caller_msisdn"` is the attribute the agent-worker reads to resolve **which customer it is talking to**.

Before this change, an unauthenticated caller of `/token` could get a join grant, but the agent always resolved the pilot subscriber, so the blast radius was "you can talk to the demo account". After this change, an unauthenticated caller can put **any MSISDN** in the request and the agent will resolve **that** subscriber's context — plan, balance, invoices, tickets — and will act on it with its write tools.

The portal itself is not the problem: `lib/api/voice.server.ts` is a `createServerFn` behind `authedMiddleware`, mints `room = portal-${session.customerId}-${suffix}` and `identity = customer-${session.customerId}` from the HMAC-signed session, and reads the MSISDN from `fetchProfileDetail()` — never from the browser. That part is exactly right. The problem is that the *endpoint* it calls has no gate, so the portal's discipline is voluntary.

**Fix (additive, ~8 lines, preserves client-widget behaviour exactly): honour `caller_msisdn` only when the request carries the internal service key.** Full code in `08-correctness-and-security-fixes.md` §8.1. In short: if `INTERNAL_API_KEY` is set and the header matches, trust `req.caller_msisdn`; otherwise ignore the field and fall back to `PILOT_MSISDN`. The client-widget sends no key and no MSISDN, so it is unaffected; the portal server already holds secrets and can send the key. No new dependency, no migration, no change to the response model.

This needs your decision only on one point: whether to make the key **required** for `/token` outright (hardest, breaks client-widget until you add the key to its env) or **required only to trust `caller_msisdn`** (recommended, zero breakage). I have written the recommended one.

---

## 3. Correctness bugs a customer will actually hit

### 3.1 A failed balance load is indistinguishable from "you have no data" (Services)

`routes/_portal/services.tsx`, verified:

```tsx
const dataBalances = (balanceQuery.data?.balances ?? []).filter(isDataBalance);
...
{dataBalances.length > 0 && (
  <PageSection label={copy.services.balances}>
    {balanceQuery.isError ? ( ...ErrorState... ) : ( ...list... )}
```

The error branch is nested **inside** `dataBalances.length > 0`. When `/me/balance` fails, `balanceQuery.data` is `undefined`, so `dataBalances` is `[]`, so the guard is false, so the whole section — **including its error state** — never renders. The customer sees a page with a plan card and nothing else, with no indication that anything failed. This is precisely the "empty states that feel broken" failure CB4 existed to prevent, and it is the only place on the branch where an error is structurally unreachable.

### 3.2 Services hides most of what `/me/balance` returns

`isDataBalance()` keeps only `balance_type === "data"` with unit `GB`/`MB`. But `me_reads.balance()` returns **every** `BalanceAccount` row (`main` credit in TND, voice minutes, SMS units) plus a `recharges` array of the last 50 top-ups. For a prepaid customer — the primary persona, per the seeded pilot data — the single most important number is the **main credit balance**, and it is on the page's data but never rendered. `recharges` is fetched and discarded everywhere in the portal.

### 3.3 The assistant's call summary never resolves the turn count

`routes/_portal/assistant.tsx`, verified:

```tsx
<MetricPair label={copy.assistant.summary.turns} value={copy.assistant.summary.turnsPending} />
```

The turn count is a permanent placeholder string. Meanwhile `me_reads.conversations()` returns `turns` per session via a `func.count()` subquery — the honest number exists on the server, one query away. And the invalidation that would fetch it is gated on write tools:

```tsx
if (session.connectionState !== "disconnected" || !hadWriteTools) return;
```

So after a purely informational call ("what is my balance?"), **Activity is never refreshed** and the call the customer just had does not appear in their history until a manual reload. Two small changes fix both: always invalidate the conversation list on disconnect, and read duration/turns for the newest session from the server instead of from `Date.now()` and a placeholder.

### 3.4 Turn ordering can invert who spoke first

`me_reads.conversation_detail()`: `.order_by(Turn.turn_index.asc(), Turn.speaker.asc())`. Using `speaker` as the tiebreaker sorts alphabetically, so within one `turn_index` an `agent` row is emitted before a `customer` row regardless of when either was recorded. `Turn.created_at` is already in the SELECT list; ordering by it is both cheaper to reason about and actually chronological.

---

## 4. Consistency gaps against CB4's own rules

| # | Where | What is wrong | Rule it breaks |
|---|---|---|---|
| 4.1 | `services.tsx` | Hand-rolled `if (isPending) return <full page skeleton>` and `if (isError) return <Card><ErrorState/></Card>` for the whole route | CB4: `DataSection` owns the four states so no screen invents a fifth; "error never replaces the whole page" |
| 4.2 | `data.tsx` `AnimatedTabs` | `layoutId="tab-underline"` is a hardcoded literal | Two tab groups on one page make the underline fly across the screen between them. Needs a per-instance id. |
| 4.3 | `data.tsx` `DataSection` | `animate={{ opacity: isFetching ? 0.55 : 1 }}` | Every background refetch (`staleTime: 30_000` + refocus) visibly dims the list. Dim only when the *page* changes, not on any refetch. |
| 4.4 | `data.tsx` `Panel` | `role="dialog" aria-modal="true"` with no focus trap, no body scroll lock, no focus restore. The comment concedes it: "focus is trapped by nothing clever" | An `aria-modal` surface that leaks focus is worse than none: screen-reader users tab into the frozen page behind it. |
| 4.5 | `data.tsx` `TopProgress` | Comment says "A 2px line"; the class is `h-px` on both wrapper and bar | Cosmetic, but the bar is currently near-invisible on high-DPI displays. |
| 4.6 | `me_reads.py` | `billing()`, `notifications()`, `callbacks()` return **no `total`/`offset`** — `notifications` and `callbacks` even discard offset (`size, _ = _page(limit, 0)`) | `Pagination` needs `total`+`limit`+`offset`. Billing invoices are hard-capped at 200 with no page control; notifications can never page. Only `conversations()` and `requests()` are pageable. |

---

## 5. Depth and organisation gaps ("content distributed the best way in the space")

This is the part of your brief that is least finished, and it is not a styling problem — it is a **content-per-tab** problem. Verified sizes tell the story:

| Tab | Route size | Reality |
|---|---|---|
| `activity.tsx` | 19,567 B | fully built |
| `billing.tsx` | 10,108 B | fully built |
| `requests.tsx` | 10,219 B | fully built |
| `assistant.tsx` | 10,636 B | fully built |
| `security.tsx` | 9,745 B | fully built |
| `profile.tsx` | 7,415 B | fully built |
| `services.tsx` | **4,699 B** | thin — one plan card grid + an optional data-only list |
| `preferences.tsx` | 4,367 B | needs an honesty decision (see §6) |
| `about.tsx` | 3,218 B | static |
| `help.tsx` | **2,781 B** | static copy from `copy.help.topics`; cards are **not** links, no destinations, no search |

Two tabs out of ten carry no data and no interaction (`help`, `about`), and one carries a fraction of the data it already fetches (`services`). On a desktop viewport that reads as three sparse pages next to seven dense ones — which is the same imbalance you originally complained about, only inverted. `10-tabs-organisation-and-visibility.md` gives each of the ten tabs an explicit spatial budget and fills `services` and `help` from data that already exists.

---

## 6. Two things I will not decide for you

**6.1 Preferences are browser-only, and one of them is a promise the portal cannot keep.**
`lib/preferences.ts` (1,740 B) is `localStorage`-backed and there is **no** `PATCH /api/v1/me/preferences` on the backend — I checked the business-api module listing; nothing was added beyond `me_reads.py`. Density/motion/theme are legitimately client-side. **Language is not.** The assistant's language comes from the customer record the agent-worker reads, not from the browser; a portal switch that says "Language: English" while the assistant keeps answering in French is a UX lie. Choose one:

- **(a) Label it honestly** — rename to "Portal display language" and add one line: "Your assistant follows the language on your account." Zero backend work.
- **(b) Make it real** — one additive `PATCH /api/v1/me/preferences` writing `customers.preferred_language`, client-scoped, no other column touched. ~40 lines, no migration.

I have written (a) as the default in CB10 because it is the truthful zero-risk option, and specified (b) fully in an appendix so you can flip to it in one commit.

**6.2 The `help` tab.** Either its six topic cards become deep links into the tabs that answer them (Compass→`/services`, ReceiptText→`/billing`, Shield→`/security`, AudioLines→`/assistant`…), or Help merges into About and the nav drops to nine destinations. Both are honest; the first keeps ten slots and costs ~20 lines, the second removes a page. CB10 specifies the first and notes the second.

---

## 7. What has never actually been executed

Stated plainly, because the results document is candid about it and it changes what "verified" means:

- `scripts/verify-portal.sh` **has never run** — the author's `bash` was a broken WSL launcher; the 12 checks were replicated by hand in PowerShell. And **CI does not run it either**: the new `customer-portal-test` job runs `npm ci`, `typecheck`, `lint`, `test`, `build` — there is no `npm run verify` step, even though `package.json` defines `"verify": "bash scripts/verify-portal.sh"`. So the guard exists, is committed, and is enforced nowhere. One CI step fixes that (CB8 §8.2).
- **No runtime was exercised at all**: no Docker, so no live LiveKit session, no real 401/403/429 path, no `pytest apps/business-api/tests`. Every `/me/*` route on this branch is compile-verified and mypy-clean but has **never returned a row**. The `_client_customer_id()` narrowing helper in `main.py` is described as "dead at runtime" — that is an assumption that only a live 403 test can confirm.
- The root `lint` job runs `ruff check .` and `mypy packages/ services/ apps/` on every `version_*` push. The results document reports 16 ruff errors and 2 mypy errors, all in files it calls "pre-existing dirty-tree". I verified that `service_health.py`, `metrics_hook.py`, and `test_service_health.py` are **not committed** on `version_93` — the business-api module listing contains no `service_health.py` — so those errors are local-only and cannot fail CI. But `repositories.py` and `packages/persistence/src/persistence/models/__init__.py` **are** committed and were also named. Whether the committed content is clean is the single thing I cannot determine without running ruff. **The first push of `version_93` will answer it definitively** — read the `lint` job, not the local shell.

---

## 8. The next batch

Four cookbooks, in dependency order. Same discipline as before: backend additions stay additive, no migration, no advisor projection widened, the orb renderer untouched, the design tokens untouched.

| Cookbook | Scope | Backend touched | Risk |
|---|---|---|---|
| **CB8** `08-correctness-and-security-fixes.md` | The P0 token trust boundary; CI runs the guard; the hidden-error bug; turn ordering; post-call refresh + real turn count; the four `data.tsx` defects | `token_service/main.py` (guarded read of an existing field), `me_reads.py` (one `order_by`) | low |
| **CB9** `09-pagination-and-data-depth.md` | `total`/`limit`/`offset` for invoices, notifications, callbacks; real pagination on Billing and Notifications; Services shows all balance types + recharges | `me_reads.py` (3 functions get counts + offset), `main.py` (3 signatures get `offset`) | low |
| **CB10** `10-tabs-organisation-and-visibility.md` | Per-tab spatial budget for all ten tabs; Services rebuilt on `DataSection`; Help deep-linked; Preferences honesty; empty-state depth; responsive column rules | none | none |
| **CB11** `11-verification-and-runtime-proof.md` | The runbook that has never been run: Docker up, live LiveKit call, 401/403/429, `pytest`, the CI verify step, and the exact expected output of each | none | none |

Merge order is CB8 → CB9 → CB10 → CB11, one commit each, on `version_94`. CB8 and CB9 are the only ones that touch Python; CB10 is pure frontend; CB11 adds no product code.

Every file in this batch was written against `version_93` as committed at `192c969c35679cdf76f6145e4f0e1776a9abdf5c`. When you cut `version_94`, the patches apply to that branch and the next review will read `version_94`.
