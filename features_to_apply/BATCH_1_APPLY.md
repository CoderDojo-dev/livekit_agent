# Batch 1 — Apply Pack (C5, C6, C7, C13)

**Base:** local `version_80` @ `eda5f58` + Features 0–4 applied + D1 retention clamp (`main.py:157`).
**Supersedes:** the per-cookbook call sites in `FEATURE_05/06/07/13` wherever this file disagrees.
**Authority for component shapes:** your `answers.md` B7 dump of `primitives.tsx`.

---

## 0. Prereq status — all green

| Prereq | Source | Status |
|---|---|---|
| D1 retention clamp (route-level 422) | `correction_results.md` §1.1 | **SHIPPED**, `-5`→422, `31`→200 |
| G3 `TableErrorRow` uses raw `<td colSpan>` | §1.2, `states.tsx:114-130` | **SAFE** — no already-shipped error row is malformed |
| G2 sanity on an applied route | §1.3, `callbacks.tsx:102-118` | **CORRECT** — F3 already uses the real label-keyed shape |
| `/sessions` route ordering | §1.4, `main.py:56` before `:71` | **CORRECT** |
| `max_frustration` null guard | §1.5, `repositories.py:141-142` | present, defensive only (A1 = 0 NULLs) |
| Lint gate baseline | §1.6 | **tsc CLEAN**, non-prettier baseline = **9 pre-existing warnings** |

### 0.1 Lint gate baseline is now a number, not a hope

The gate for every cookbook in this batch:

```
bunx tsc --noEmit                       # exit 0
bun run lint 2>&1 | grep -v 'prettier/prettier'   # exactly 9 findings, no new ones
bun run build                           # exit 0
bunx prettier --write <touched files only>
```

The 9 are `react-refresh/only-export-components` ×7 and `react-hooks/exhaustive-deps` ×2, all in
Feature 0–4 files. **Do not fix them in this batch** — they are the baseline, and touching them makes
the delta unreadable. If the count moves off 9, the cookbook introduced it.

Never run `bun run format`. It is `prettier --write .` across a repo with 2704 prettier findings.

---

## 1. Open item promoted from your §1.4 — `/sessions` role gate

You found `GET /api/v1/sessions` returns **403** for `conseiller`; my runbook §3 expected 200.

**My call: keep the `superviseur` gate. My runbook expectation was wrong, not the code.**

Reasons:

1. Feature 4 chose *list = superviseur, detail = conseiller* deliberately, it is applied, documented, and
   passing. An applied-and-documented decision outranks an unapplied runbook line.
2. It is consistent with every other aggregate surface: `/escalations`, `/kpis`, `/actions`,
   `/policy/verdicts`, `/telemetry/timeline` are all `superviseur`. A cross-customer session list is an
   aggregate; a single session opened from a customer file is not.
3. **C13 depends on this being the rule.** `/escalations` is `superviseur`, and C13's UI links out to
   session detail. If the list gate were lowered to `conseiller`, C13 would be the only superviseur-gated
   list in a sea of conseiller lists, and the role model would stop being explainable.

So: no change, and I am writing the rule down as an invariant rather than leaving it as a coincidence —
**aggregate/cross-entity lists are `superviseur`; single-entity reads reached from an entity you already
hold are `conseiller`.** C5, C6, C7, C13 follow it.

---

## 2. Q1 accepted — C13 stays read-only

Your answer confirms what the data implied: **58/58 open, `resolution` never written by anything.** There
is no close path to wire, and inventing one would be new business logic.

C13 ships read-only. `resolution` is already in the `/escalations` payload, so the column lights up on its
own the day a close path exists — **C13 needs no revision at that point.** That is why I put the mapping
in now (`null→open`, `transferred→in_progress`, `queued→queued`, `callback_scheduled→pending`,
`resolved→resolved`) even though only `null` occurs today: it is dead code that costs nothing and prevents
a blank chip later.

One consequence worth stating plainly: **the escalations page will show 58 rows all reading "open", and
that is correct, not a bug.** It is the honest rendering of a system with no closure mechanism. Do not let
it read as a UI failure at review time.

## 3. Q2 accepted — Phase 2 stays scoped

Agreed and recorded. Phase 2 remains `guards.ensure_identity_verified` only.

But I am not leaving the `ticket_tools` finding as prose in a report, because it will be lost. It is the
same defect shape as the one already patched — six tools (`create_support_ticket`,
`check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`,
`delete_support_ticket`) all route through `_mcp_call()`, which does `streamablehttp_client` +
`ClientSession` + `httpx` I/O **without `context.foreground()`**.

**C5 is the tickets cookbook, and it makes this observable.** Once C5 is applied you can see, per ticket,
whether it was created by the agent and when. That gives you the reproduction path you currently lack:
trigger a ticket action in a call, and if the agent goes silent, the in-flight tool is known by
construction. **No inference required — the answer becomes a fact.** That is a better reason to apply C5
first in this batch than any UI consideration.

---

## 4. Mandatory call-site corrections — apply to all four cookbooks

These three defects are mine. They are in every cookbook, and they are compile-breaking. Fix them as you
apply, not afterwards.

### G1 — `SearchInput.onChange` receives a **string**

Real signature (`primitives.tsx:471`): `onChange?: (value: string) => void`, `type="search"`.

```tsx
// WRONG — what my cookbooks wrote
<SearchInput value={search} onChange={(e) => setSearch(e.target.value)} />

// RIGHT
<SearchInput value={search} onChange={(value: string) => setSearch(value)} />
```

Affects: **C5, C6, C11, C14** (C13 uses a search field too — check it).

### G2 — `Tabs` / `Segmented` are **label-keyed**

Real signatures (`:509`, `:544`): `items: string[]`, `active: string`, `onSelect?: (item: string) => void`.
There is no `value`, no `onChange`, no `{label, value}` object.

Use a label↔id map. Do not thread raw labels through state — the id is what the API takes.

```tsx
const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
}
const STATUS_BY_LABEL = Object.fromEntries(
  Object.entries(STATUS_LABEL).map(([id, label]) => [label, id]),
) as Record<string, TicketStatus>

const labels = Object.values(STATUS_LABEL)

<Segmented
  items={labels}
  active={STATUS_LABEL[status]}
  onSelect={(label) => setStatus(STATUS_BY_LABEL[label])}
/>
```

This is exactly the shape `callbacks.tsx:102-118` already uses — **copy that file's pattern rather than
mine.** It is applied, reviewed, and passing.

Affects: **C5, C6, C11, C13, C14** (and C3, already correct).

### G3 — `Td` has **no** `colSpan`

Real signature (`:446`): `{ children?, className?, align? }`. Spanning cells must be raw `<td>`.

```tsx
// WRONG
<Td colSpan={6}><EmptyState … /></Td>

// RIGHT
<td colSpan={6} className="px-sp-7 py-sp-8">
  <EmptyState icon={Inbox} title="No tickets" description="…" />
</td>
```

`px-sp-7 py-sp-8` matches the padding `TableShell` rows use, so the empty state sits centred in the body
rather than crushed against the first column.

Affects: **every empty-state and spanning row in C5, C6, C7, C8, C9, C10, C11, C12, C13, C14.**
Error rows are already safe — `TableErrorRow` takes `colSpan` and renders raw `<td>` (your §1.2).

---

## 5. Per-cookbook deltas beyond G1/G2/G3

### C5 — Tickets

- **Status chips are safe as-is.** `ticketing.py` uses `open` / `resolved`; both exist in `status.ts`.
  Live data is `open` 19 / `resolved` 2. `in_progress` and `closed` also exist in the truth table, so the
  full mapping is chip-safe with no `status.ts` edit. **Fifteenth consecutive cookbook with zero
  `status.ts` changes** — the truth table has held.
- 21 tickets total, so pagination is cosmetic. Ship the limit clamp anyway; it is 2 lines.
- `ticketing-glpi` is **Up but not healthy** (your B1). Ticket *reads* come from Postgres, so C5 renders
  fine regardless — but do not read a healthy tickets page as evidence that GLPI is healthy.

### C6 — Knowledge / RAG

- `ready → indexed` mapping stands (`ready` is absent from `status.ts`).
- `KNOWLEDGE_API_URL` is **unset** locally → code default `http://localhost:8102`. From inside the
  TanStack server process that resolves to the host, not the container. If uploads fail with a connection
  error, set it explicitly rather than debugging the frontend.
- The whole knowledge service is behind `require_internal_key`; `INTERNAL_API_KEY=dev-key-123` is set
  (H-4), so it works locally and **must not ship that value anywhere else**.
- `formatBytes` exists in `format.ts` — use it for document sizes, do not hand-roll.

### C7 — Guardrails / Policies

- Smallest cookbook in the batch (594 lines) and **zero backend files**. `/api/v1/reference/business-rules`
  already returns `policy_view.overlay(rows)`.
- Booleans → `active` / `inactive` chips (the blank-chip trap, recurrence 7 of 13).
- Unit suffixes are presentational only: `*_tnd` → `" TND"`, `*_days` → `" days"`, `*_per_year` → `"/year"`.
  **Do not** use `formatCurrency` on `*_tnd` values — it takes **cents**, and these are `Numeric(12,2)`
  decimal units. It would divide your policy caps by 100.
- `business_rules` has 6 rows, all populated. `GOVERNED_BY` links two rules to `POLICY_*` env vars; the
  overlay source string is `"policy-engine (POLICY_* env)"` — surface it, so a reviewer can tell which
  numbers come from env and which from the table.
- **D13 invariant to write into the deploy docs while you are here:** `policy-service` and `business-api`
  must read the same `POLICY_*` file. Locally both use `env_file: [../../.env]`, so they agree by accident.
  In any split deployment, they will silently disagree and the dashboard will confidently show numbers the
  engine is not enforcing.

### C13 — Escalations

Three changes from the shipped cookbook:

1. **Backend is no longer zero-file.** `/escalations` emits `{id, session_id, trigger, target, resolution,
   dossier}` — **no `created_at`, no `customer_id`** (your B4). The list cannot be sorted by time or linked
   to a customer without them. Add two keys to the existing dict in `repositories.py`; the query already
   orders by `EscalationCase.created_at.desc()`, so the data is in hand and this adds no round trip.
   `customer_id` comes via the session join.
2. **`target` is always `manager_agent`; `human_advisor` never occurs.** Both are absent from `status.ts`,
   so render `target` as a `Token`, not a chip. Do not build UI that implies a human-handoff path exists.
3. **Remove the ingestion panel from `conversations.tsx` before deleting `INGESTED_FILES`.**
   `INGESTED_FILES` is still imported at `conversations.tsx:15` and used at `:149` and `:162`. C13 retires
   `/conversations` in favour of `/escalations`, which resolves it — but the deletion order matters:
   **retire the route first, then delete the mock.** Reversed, the build breaks between commits.

Also soften **B12/C4**: your A10 shows **zero `turn_index` gaps** (`count(turns) == max(turn_index)` for
every session). Dropped writes are *possible by design* (`writer.py` logs and drops when the DB is down) —
they are **not observed**. State it as a resilience property, not a data-integrity warning.

---

## 6. Apply order

1. **C5 Tickets** — 0 backend files. Delivers the Q2 reproduction path (§3).
2. **C6 Knowledge** — 0 backend files. Independent surface.
3. **C7 Policies** — 0 backend files. Smallest; also lands the D13 note.
4. **C13 Escalations** — **2 backend dict keys**, retires `/conversations`, deletes `INGESTED_FILES`.

Backend-touching and route-retiring work goes **last**, so the first three commits stay trivially
revertible. One commit per cookbook. Run the §0.1 gate after each, not once at the end — otherwise a
failure cannot be attributed.

### Shared-file collisions inside this batch

| File | C5 | C6 | C7 | C13 |
|---|---|---|---|---|
| `src/lib/nexus/query-keys.ts` | + | + | + | + |
| `src/lib/nexus/nav.ts` | | | | + (retire `/conversations`, add `/escalations`, `G E`) |
| `src/lib/nexus/data.ts` | − mocks | − mocks | − `POLICIES` | − `INGESTED_FILES`, `CONVERSATIONS`, `THREAD` |
| `routeTree.gen.ts` | | | | regenerated |

`routeTree.gen.ts` is regenerated by `@tanstack/router-plugin` on dev/build — there is **no routeTree
script** (your B10). Do not hand-edit it; run `bun run build` and commit the result.

All four touch `query-keys.ts`. Append-only, distinct key namespaces (`ticketKeys`, `knowledgeKeys`,
`policyKeys`, `escalationKeys`) — conflicts are trivial but **apply sequentially**, not in parallel.

---

## 7. Batch gate (run once, after all four)

1. `bunx tsc --noEmit` → exit 0
2. non-prettier lint findings → **still exactly 9**
3. `bun run build` → exit 0
4. Every nav entry resolves; no dead link to `/conversations`
5. Shortcuts `G A`, `G D`, `G K`, `G E` all navigate
6. `grep -rn 'INGESTED_FILES\|CONVERSATIONS\|THREAD\|POLICIES' src/` → no hits outside `data.ts` deletions
7. `curl -H 'X-Role: superviseur' …/api/v1/escalations` → 200, payload contains `created_at` **and**
   `customer_id`
8. `curl -H 'X-Role: conseiller' …/api/v1/escalations` → **403** (the §1 invariant holds)
9. DB unchanged: 129 sessions, 490 turns, 21 tickets, 58 escalations, `action_ledger` still 0

---

## 8. What I need from you to emit the flat `git apply` diff

I can emit byte-exact, `git apply`-able hunks for **new files** — they are fully determined by the
cookbooks. I **cannot** do it honestly for the six files that Features 0–4 already modified, because a
unified diff needs the exact current bytes and I have never read their post-F4 state. Guessing context
lines produces a patch that fails to apply, which is worse than no patch.

Dump these and I will emit the flat diff for batch 1:

```
cd Frontend/admin_dashboard
cat -n src/lib/nexus/query-keys.ts
cat -n src/lib/nexus/nav.ts
cat -n src/components/nexus/states.tsx
sed -n '1,60p' src/lib/nexus/data.ts
grep -n 'INGESTED_FILES\|CONVERSATIONS\|THREAD\|POLICIES\|RULES' src/lib/nexus/data.ts
cd ../.. && sed -n '/def escalations/,/return/p' apps/business-api/src/business_api/repositories.py
```

Without them, the cookbooks still apply — they use anchored find-and-replace, which tolerates drift.
The flat diff is the optimisation, not the mechanism.
