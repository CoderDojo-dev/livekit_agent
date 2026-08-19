# Review of version_96 + audit map for the client portal

Branch read: `CoderDojo-dev/livekit_agent` @ `version_96`, tree commit `fa220abc85ed498bc83e158d6596d4510b87441f`.
Results file read: `patch-v96-topbar-key-and-missing-tests-results.md` (8,355 B, in full).

Every statement below was verified by reading the file on the branch. Nothing here is carried over on trust from a previous results document.

---

## 1. v96 claims, checked against the branch

| Claim in the v96 results file | Branch verdict |
|---|---|
| CB16.1 topbar key scoped to the customer | CONFIRMED. `portal-topbar.tsx` no longer holds the unscoped `["me","profile","detail"]`; `qk.profileDetail` is the shape in `query-keys.ts:9`. |
| CB16.2 both regression test files committed | CONFIRMED present in the tree. |
| `qk` is customer-scoped everywhere | CONFIRMED. All 11 factories in `query-keys.ts` take `cid` first. |
| 13/13 verify-portal checks pass | Not re-runnable from here (no bash against the repo). Accepted as reported. |
| 8 failures in `test_agent_activity_speaker.py` are live-data contamination | Accepted. The diagnosis is sound: the tests assume a clean 24h window. Option A (leave as-is) is the correct call; weakening a real assertion to accommodate real data would be worse. |

**v96 is a clean, honest patch.** CB16 landed exactly as described. No regressions found.

---

## 2. The three functional defects the user reported — all three reproduce on the branch

All three are real, all three have a confirmed root cause, and none of them is a cosmetic problem.

### 2.1 Billing page crashes — ROOT CAUSE FOUND

The reported text is exactly `copy.errors.brokenTitle` + `copy.errors.brokenBody`:

```
brokenTitle: "This page did not load",
brokenBody: "Something went wrong on our side. Try again, or go back to the start.",
```

Those two strings are rendered **only** by `ErrorComponent` in `src/routes/__root.tsx`, which is the router's `errorComponent`. That is a whole-page error boundary, not the inline `ErrorState` that `billing.tsx` uses for query failures.

**Therefore billing is not failing its fetch. It is throwing during render.** That single deduction is what localises the bug.

The throw:

1. `me_reads.billing()` returns, for a customer with **no billing accounts**:
   ```python
   return {
       "accounts": [],
       "total_outstanding": 0.0,
       "next_due_date": None,
       "currency_code": "",          # <-- empty string
       ...
   }
   ```
2. `billing.tsx` renders the amount-due tile unconditionally:
   ```tsx
   value={billing ? money(billing.total_outstanding, billing.currency_code) : ""}
   ```
3. `format.ts` `money()` guards the *value* but never the *currency*:
   ```ts
   export function money(value: number | null | undefined, currency = "TND"): string {
     if (value === null || value === undefined) return "-";
     return new Intl.NumberFormat(LOCALE, { style: "currency", currency, ... }).format(value);
   }
   ```
   The default parameter `= "TND"` only applies when the argument is `undefined`. `""` is not `undefined`, so `""` is passed straight through.
4. `new Intl.NumberFormat("en-GB", { style: "currency", currency: "" })` throws
   `RangeError: Invalid currency code : ` — per ECMA-402, `style: "currency"` requires a well-formed 3-letter ISO 4217 code.
5. The RangeError propagates out of render into the root `errorComponent`. The customer sees "This page did not load".

**Who this hits:** every prepaid-only customer, i.e. anyone with zero rows in `billing.accounts`. Yousra (prepaid) is exactly this profile. A postpaid customer such as Amine has accounts, gets a real `currency_code`, and never sees the crash. That precisely matches a bug that looks intermittent but is in fact deterministic per account type.

**Correct layer to fix:** `lib/format.ts`. One function, guarding one precondition, protects every call site at once — the amount-due tile, every invoice row, the invoice detail panel, and `quantity()` which delegates to `money()` for TND balances. Fixing it in `billing.tsx` instead would leave the same landmine in `services.tsx` and the invoice panel.

A second, latent instance of the same class of bug is on the adjacent lines:
```tsx
const invoices = billing?.invoices.items ?? [];
const invoiceTotal = billing?.invoices.total ?? 0;
```
The optional chain stops at `billing`. If `invoices` were ever absent or null the property read throws. The backend always sends it today, so this is not the active crash - but it is one contract change away from being one.

Full patch: cookbook 17, section 17.1.

### 2.2 `[object Object]` in a previous conversation — ROOT CAUSE FOUND

`activity.tsx`, `ConversationBody`:

```tsx
[copy.activity.turns, String(detail.turns)],
```

`detail` is a `ConversationDetail`. The types in `activity.server.ts` are explicit:

```ts
export type ConversationSummary = { ...; turns: number };
export type ConversationDetail  = Omit<ConversationSummary, "turns"> & { turns: ConversationTurn[] };
```

So the **same field name carries two different types on two different endpoints**, and the backend confirms it:

- `me_reads.conversations()` (list) emits `"turns": int(row.turns)` - a count.
- `me_reads.conversation_detail()` emits `"turns": [ {index, speaker, agent, language, text, at}, ... ]` - the transcript.

`String([{...},{...}])` is `"[object Object],[object Object]"`. Eleven turns produce exactly the eleven repetitions the user photographed. The file even proves the array nature twelve lines further down, where it correctly does `detail.turns.length > 0` and `detail.turns.map(...)`.

This is not a data problem, not a legacy-shape problem, and not a backend problem. The API contract is correct and the transcript below the metric renders fine. It is one wrong expression in one cell.

**Correct layer:** the component, plus a type-level guard so the trap cannot be re-entered. Full patch: cookbook 17, section 17.2.

### 2.3 Conversation starts in Arabic / switches language — ROOT CAUSE FOUND

French **is** correctly configured as the default in three places:

- `config/settings.py`: `default_language: "fr"`, `session_language: "fr"`, `supported_languages: "fr,ar,en"`.
- `providers/language_router.py`: `LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])`.
- `providers/stt.py`: STT is built for **one** pinned language (`preset["deepgram_language"]`), with an explicit comment that Arabic uses the monolingual `ar` model and never `multi`.

That last point is important and rules out a whole class of suspicion: **the STT layer cannot auto-detect and cannot silently switch languages.** So the wrong language must be chosen *before* the session starts.

It is. `server.py`:

```python
language = settings.session_language          # "fr" - correct
...
user_data = await _prefetch_user_data(language, participant)
language = user_data.language                 # <- overwritten here
...
session = build_agent_session(settings, language, keyterms)
await session.start(agent=TriageAgent(language=language), room=ctx.room)
```

and inside `_prefetch_user_data`:

```python
snapshot = await get_context_client().get_snapshot(msisdn)
if snapshot is not None:
    user_data.customer_context = snapshot
    user_data.language = snapshot.preferred_language   # unconditional override
```

`snapshot.preferred_language` is a CRM column. It is assigned with:

- **no allow-list check** against `settings.languages`;
- **no precedence rule** - it silently outranks the configured default;
- **no null/empty guard** - an empty or unknown value flows into `GREETINGS[language]` and `TriageAgent(language=...)`.

So the session language is whatever the CRM row happens to say. For a Tunisian telecom seed set, `preferred_language = "ar"` on some customers is entirely expected. The conversation therefore "sometimes starts in Arabic" - deterministically per customer, which reads as random when you switch test accounts.

Note also `copy.profile.fields.scopeNote`, which documents the current decision to the customer: *"The language your assistant speaks follows your account and is set when you speak to us."* The CRM value being authoritative is **intentional**. What is missing is that it must be *validated* and *rankable*, and that the customer has no way to set it.

**Correct layer:** the composition root (`server.py`) plus a small resolver, so precedence is stated once in code rather than implied by assignment order. Full patch: cookbook 18.

---

## 3. Audit map of the portal

| Area | File | Verdict |
|---|---|---|
| Auth / session gate | `routes/_portal.tsx` | Correct. UX gate only; real boundary is `authedMiddleware`. Expiry bounce present. |
| Shell / rail / topbar | `components/shell/portal-shell.tsx` | Correct. One scroll region, collapsible rail, sticky topbar. |
| Topbar profile cache | `components/shell/portal-topbar.tsx` | Correct as of v96 (CB16.1). |
| Query keys | `lib/query-keys.ts` | Correct. All customer-scoped. |
| Formatters | `lib/format.ts` | **BROKEN** - `money()` unguarded currency. Causes the billing crash. |
| Billing | `routes/_portal/billing.tsx` | **BROKEN** via `money()`. Structure, paging, panel, prepaid pointer all correct. |
| Activity list | `routes/_portal/activity.tsx` | Correct. |
| Activity detail | `routes/_portal/activity.tsx` `ConversationBody` | **BROKEN** - `String(detail.turns)`. |
| Activity cards | same | Partially implemented - numbers only, no visual metric. Section 9 of the brief. |
| Assistant | `routes/_portal/assistant.tsx` | Partially implemented - single centred column, no two-column call layout, no height containment. |
| Live transcript | `components/assistant/live-stream.tsx` | Correct behaviour, wrong placement. Caps at 3 visible items, so it cannot grow the page unboundedly - useful. |
| Data states | `components/portal/data.tsx` | Correct and complete. `DataSection` owns all four states. |
| Primitives | `components/portal/primitives.tsx` | Correct but plain. `Button` has no press/hover motion, radius capped at `--r-2`. |
| Theme tokens | `src/styles.css` | Dark only. 13 greys under `:root`, no light scope, no grid. |
| Preferences | `lib/preferences.ts` | Correct, localStorage + data-attributes. **No theme key, no language key.** |
| Branding | `__root.tsx`, `copy.ts`, all route heads | **"Nexus" throughout** - `copy.brand.name`, `copy.login.title`, every route `<title>`, `og:*`, `twitter:site`, `author`, and the `nexus_portal_preferences` storage key. |
| Reduced motion | `styles.css` + `preferences.ts` | Correct, both OS and manual. |
| Accessibility | across | Good baseline: `focus-ring`, `aria-live`, `role="switch"`, focus trap + restore in `Panel`. |

---

## 4. Gap analysis and priority

**Broken - fix first (cookbook 17, 18)**
1. Billing crash (`money()` currency guard). Highest severity: a whole tab is dead for prepaid customers.
2. `[object Object]` turns cell.
3. Language precedence + allow-list.

**Partially implemented - complete (cookbook 19, 20)**
4. Assistant two-column call layout + no-scroll composition.
5. Activity card visual metric.
6. Branding de-Nexus.
7. Premium grid background.
8. Light mode.
9. Button refinement.

**Already correct - do not touch**
- Paging and offset on every reader (v95/CB12).
- Customer-scoped cache keys and logout sweep (v95/v96).
- `DataSection` four-state contract.
- `vip` stripping at the route boundary.
- Notifications in the Activity "Messages" secondary tab.
- The `Orb` component and `orb/` directory. `git diff` on `styles.css` and `components/orb` was clean in v95 and must stay that way for the orb internals.

**Intentional decisions to preserve**
- Strictly achromatic palette: every colour satisfies R === G === B. Light mode must obey this too - greys only, no hue.
- Radius ceiling 12px (`--r-5`), no perfect circles. The button work must respect this; "more rounded" stops at `--r-3`.
- Status is communicated by **shape**, not hue (`StatusChip` tones are solid/outline/dashed/dotted/muted). Do not add colour-coded status.
- No preferences are persisted server-side, because no preferences table exists. Cookbook 18 respects this: the language preference is stored in the existing CRM column via the existing profile write path, not in a new invented table.
- Payments stay an unpaged recent list by design.
- Whole-account billing figures deliberately do not follow the invoice page.

**Out of scope / blocked**
- The `policy-service -> postgres` compose build failure. Open since v95, unrelated to the portal.
- The 8 `test_agent_activity_speaker.py` failures. Environmental, Option A already chosen.
- Live-call verification (9 orb states, tool events, greeting). Needs a microphone and a running LiveKit; only the user can do this.

---

## 5. Cookbook order

Apply in this order. 17 first because a dead billing tab outranks everything cosmetic.

| Cookbook | Scope | Risk |
|---|---|---|
| 17 | Billing crash + `[object Object]` + regression tests | Very low. 2 expressions, 1 guard, 2 test files. |
| 18 | Language precedence, allow-list, preferred-language setting | Low-medium. Touches the composition root. |
| 19 | Assistant two-column + no-scroll | Medium. Layout only, no logic change. |
| 20 | Branding, grid, light mode, buttons, activity metric | Medium. Broad but mechanical. |

Nothing in 17-20 changes an API contract, adds a dependency, or touches the orb internals.
