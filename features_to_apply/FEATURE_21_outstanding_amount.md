# FEATURE_21 — Expose `Invoice.outstanding_amount` in the customer 360 open-invoices panel

> Branch of truth: `version_81`. Applied on top of the uncommitted F15 + F16 + F17 + F18 + F20 working tree.
> Cookbook path: `features_to_apply/FEATURE_21_outstanding_amount.md`
> Scope: **one additive key** on an existing projection + its frontend consumption. No new route, no new query key, no migration, no new dependency.
> This is the §6-B follow-up FEATURE_20 flagged and did not build.

---

## §0 — Preconditions (read before applying)

### 0.1 This cookbook assumes FEATURE_20 / C-1 is already applied

Every `customer-view.ts` and `customer-detail.tsx` anchor below is written against the **post-C-1** tree:

| Symbol | Pre-C-1 | Post-C-1 (assumed here) |
| --- | --- | --- |
| Helper | `outstandingTotal` | `unpaidTotal` |
| Status guard | *(none)* | `OWED_STATUSES` |
| Footer label | `Total invoiced` | `Unpaid total` |

Confirm before starting:

```bash
git grep -n "unpaidTotal" -- Frontend/admin_dashboard/src
# expect exactly 3 hits: definition, import, call site
```

If that returns 0, stop — apply FEATURE_20 / C-1 first.

### 0.2 Do NOT byte-match the FEATURE_20 text

FEATURE_20 gate #3 recorded that `prettier --write` **reformatted `customer-view.ts`** on apply. The text now in the tree may not be byte-identical to what FEATURE_20 §4.1 printed. Every `customer-view.ts` instruction in §4.3 is therefore expressed as **two token substitutions plus a JSDoc sentence**, not as a block replacement. Do not attempt a whole-function `oldStr` match.

### 0.3 Run the falsifiability check FIRST — before touching any file

This feature is only visible if `outstanding_amount` actually differs from `total_amount` on at least one row. Seed data may have set them equal, in which case this patch is future-proofing and **the displayed number will not move** — exactly the "latent pass" outcome FEATURE_20 / C-1 hit. Establish which case you are in *before* you write code, not after:

```sql
-- docker exec -it <postgres> psql -U telecom -d telecom
SELECT i.customer_id,
       i.invoice_number,
       i.status,
       i.total_amount,
       i.outstanding_amount,
       (i.total_amount - i.outstanding_amount) AS delta
FROM billing.invoices i
ORDER BY i.status;
```

Record the output. Two possible worlds:

| World | Meaning | What to do |
| --- | --- | --- |
| **Some `delta <> 0`** | Real partial payments exist. This patch changes a visible number. Full end-to-end proof available. | Apply as written; §5.4 will show a moved value. |
| **All `delta = 0`** | Seed data never recorded a part-payment. Patch is correct but invisible today. | Apply as written, then record it in the results as a **latent pass**, exactly like FEATURE_20 item 19. Do not claim a visible fix. |

The expected shape from the last known state of this DB is 2 rows (`overdue` ×1, `partial` ×1). A `partial` invoice whose `delta = 0` is itself a data inconsistency worth noting in the results — it means the status says part-paid while the balance says nothing was paid.

---

## §1 — Feature name & scope

**Name:** True remaining balance in the 360 open-invoices panel.

**The defect.** `SupervisionRepository.customer_360()` projects `float(i.total_amount)` — the invoice **face value** — under the key `amount`. The 360 modal sums that projection and, after FEATURE_20 / C-1, labels the result **"Unpaid total"**. On any invoice with `status = 'partial'` those are different numbers: the customer has already paid part of it. `Invoice.outstanding_amount` holds the real remaining balance, is `nullable=False` with `server_default 0`, and is **never projected anywhere in the API**.

So the panel currently overstates what a part-paying customer owes, by exactly the amount they have already paid.

**In scope**

1. Add one key, `outstanding`, to the `open_invoices` projection in `customer_360()`.
2. Add the matching field to the `CustomerInvoice` wire type.
3. Make `unpaidTotal` sum the remaining balance instead of the face value.
4. *(§6-A dependent)* Show the face value as a row caption when the two differ, so the rows still add up to the footer.

**Out of scope — deliberately**

| Not doing | Why |
| --- | --- |
| Changing the `!= "paid"` server-side filter | FEATURE_20 §6-C already refused this. Constraint 2 — locked backend core logic. C-1 handles it display-side. |
| Removing or renaming `amount` | Removal is a breaking change to an existing key. Additive only, per the C13 precedent. |
| Any new endpoint, query key, or nav entry | None needed. |
| A `paid_to_date` derived key | `total_amount - outstanding_amount` is derivable client-side; a third money key on the wire earns nothing. |

---

## §2 — Backend reference (exact names and paths)

### 2.1 The projection being changed

`apps/business-api/src/business_api/repositories.py` → `class SupervisionRepository` → `customer_360()`. The list comprehension, verbatim from the branch:

```python
"open_invoices": [
    {"invoice": i.invoice_number, "amount": float(i.total_amount), "status": i.status}
    for i in invoices if i.status != "paid"
],
```

### 2.2 The column being exposed

`packages/persistence/src/persistence/models/billing.py` → `class Invoice`, verbatim:

```python
total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
outstanding_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
```

Both are `Numeric(12, 2)`, both `nullable=False`, both `server_default 0`. Consequences that matter:

- **`float(i.outstanding_amount)` can never raise on `None`.** The column is NOT NULL, so no guard is needed — the same reasoning that makes the existing `float(i.total_amount)` safe. This is the one place in this cookbook where a null-guard is *correctly* absent, and it is absent for a reason recorded here (contrast the F17 №5 / F18 №7 `formatInstant` lessons, where the column *was* nullable).
- **Both serialise to 2-decimal JSON numbers.** Strict `!==` comparison between them in TypeScript is sound; no epsilon needed.
- **No new import.** `Invoice` is already imported in `repositories.py` via `from persistence.models.billing import Invoice`. The sqlalchemy import line is untouched.

### 2.3 The precedent this follows

The C13 audit follow-up added `created_at` and `customer_id` to the `escalations()` dict, with the approval recorded inline in `repositories.py`. That is the sanctioned pattern for widening an existing projection: **additive keys only, never a removal or a rename.** FEATURE_21 is the same move on a different method.

The frontend half of that precedent is in `Frontend/admin_dashboard/src/lib/api/escalations.server.ts`, verbatim:

```ts
  dossier: Record<string, string | number | boolean | null>;
  /** Batch 1 / C13 — added to the repository dict (additive). */
  created_at: string | null;
  customer_id: string | null;
```

§4.2 copies that JSDoc form exactly.

---

## §3 — Endpoints

### 3.1 Existing, reused unchanged

| Concern | Value |
| --- | --- |
| Route | `GET /api/v1/customers/{customer_id}/360` |
| Role | `conseiller` (unchanged) |
| Handler | `customer_360` in `apps/business-api/src/business_api/main.py` |
| Server fn | `getCustomer360` in `src/lib/api/customers.server.ts` |
| Query key | `customerKeys.detail(customerId)` |

### 3.2 New endpoints

**None.** No CORS hunk, no middleware change, no `main.py` diff at all.

### 3.3 Response delta

Only `open_invoices[]` changes, and only by gaining a key:

```diff
 "open_invoices": [
   {
     "invoice": "INV-2026-0001",
     "amount": 300.0,
+    "outstanding": 120.0,
     "status": "partial"
   }
 ]
```

Every existing consumer of `amount` keeps working. This is why the key is added rather than repurposed.

---

## §4 — Implementation plan

Four files. Apply in this order — backend first, so `tsc` sees a real shape when you reach the frontend.

### 4.1 `apps/business-api/src/business_api/repositories.py`

**Anchor on the dict literal line only.** Do not anchor on the `for ... if ...` line; its wrapping is not worth depending on.

Confirm the anchor is unique first:

```bash
git grep -c "i.invoice_number" -- apps/business-api/src/business_api/repositories.py
# expect: 1
```

`oldStr`:

```python
            {"invoice": i.invoice_number, "amount": float(i.total_amount), "status": i.status}
```

`newStr`:

```python
            {
                "invoice": i.invoice_number,
                "amount": float(i.total_amount),
                # FEATURE_21 — additive key (same precedent as the C13 keys on escalations()).
                # `amount` is the invoice face value; `outstanding` is what is still owed.
                # Both columns are NOT NULL with server_default 0, so neither needs a guard.
                "outstanding": float(i.outstanding_amount),
                "status": i.status,
            }
```

Notes:

- Match the surrounding indentation of the file; the leading whitespace shown above is illustrative. The dict sits one level inside the list comprehension, which sits inside the returned dict.
- `outstanding` is placed **between** `amount` and `status`, so the two money keys read together.
- Ruff config ignores `E501`, but the multi-line form is used anyway to stay under 110 columns and keep the comment attached to the key it explains.
- No import change. `Invoice` and the sqlalchemy import line are both untouched.

### 4.2 `Frontend/admin_dashboard/src/lib/api/customers.server.ts`

One type gains one field. Nothing else in this file changes — in particular **`getCustomer360` keeps its `raw: unknown` inputValidator**. This file does not use zod, and per the FEATURE_18 №4 lesson the rule is *clone the sibling you are editing*, not *prefer one form globally*. `tickets.server.ts` and `escalations.server.ts` use zod; `customers.server.ts` does not; leave it that way.

`oldStr`:

```ts
export type CustomerInvoice = {
  invoice: string;
  amount: number;
  status: string;
};
```

`newStr`:

```ts
export type CustomerInvoice = {
  invoice: string;
  /** Invoice face value (`total_amount`). */
  amount: number;
  /** FEATURE_21 — added to the repository dict (additive). Balance still owed. */
  outstanding: number;
  status: string;
};
```

The second JSDoc line copies the C13 comment form in `escalations.server.ts` verbatim in structure.

### 4.3 `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts`

**Two token substitutions and one JSDoc sentence, inside `unpaidTotal`.** Expressed this way because §0.2 — the block was prettier-reformatted on apply and a whole-function match is not safe.

| # | Find (inside `unpaidTotal` only) | Replace with |
| --- | --- | --- |
| 1 | the parameter's `amount: number` | `outstanding: number` |
| 2 | the reducer's `i.amount` | `i.outstanding` |
| 3 | the JSDoc sentence | see below |

JSDoc, replacing whatever C-1 left there:

```ts
/**
 * Sum of the balance still owed across invoices in an owed status, for the panel's
 * summary line. FEATURE_21 — sums `outstanding` (remaining balance), not `amount`
 * (face value); on a partial invoice those differ by whatever has already been paid.
 */
```

The function should end up equivalent to:

```ts
export function unpaidTotal(
  invoices: Array<{ outstanding: number; status: string }>,
): number {
  return invoices
    .filter((i) => OWED_STATUSES.has(i.status))
    .reduce((sum, i) => sum + (Number(i.outstanding) || 0), 0);
}
```

Do not touch:

- **`OWED_STATUSES`** — C-1's status narrowing is orthogonal and stays exactly as applied.
- **The function name.** It still sums what is unpaid; it now does so correctly. Renaming it to `outstandingTotal` would resurrect the identifier C-1 just deleted, and would make the results report of two consecutive features contradict each other.
- **`formatAmount`** — unchanged, and still the correct formatter (`customer-view.ts`'s own, *not* `format.ts`'s `formatCurrency`, which expects cents).

### 4.4 `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx` *(§6-A option A only)*

If §6-A resolves to **B** or **C**, skip this file entirely and the patch is three files.

The problem this solves: once the footer sums `outstanding` but each row still prints `amount`, the visible rows no longer add up to the visible total. Option A keeps the arithmetic legible by showing the remaining balance as the row's primary figure and the face value as a caption — **and only when they differ**, so unpaid-in-full invoices are visually unchanged.

`oldStr` (verbatim from the branch; C-1 did not touch this block):

```tsx
                      <span className="t-ui truncate text-ink-1">{inv.invoice}</span>
                      <span className="ml-auto flex items-center gap-sp-5">
                        <span className="t-mono-l text-ink-1">{formatAmount(inv.amount)}</span>
                        <StatusChip status={invoiceStatusKey(inv.status) ?? ""} />
                      </span>
```

`newStr`:

```tsx
                      <span className="min-w-0">
                        <span className="t-ui truncate text-ink-1">{inv.invoice}</span>
                        {inv.outstanding !== inv.amount ? (
                          <span className="t-caption truncate text-ink-4">
                            Invoiced {formatAmount(inv.amount)}
                          </span>
                        ) : null}
                      </span>
                      <span className="ml-auto flex items-center gap-sp-5">
                        <span className="t-mono-l text-ink-1">{formatAmount(inv.outstanding)}</span>
                        <StatusChip status={invoiceStatusKey(inv.status) ?? ""} />
                      </span>
```

> **Apply by editing the two changed spans in place**, not by pasting the block wholesale — the wrapping `<li>`, its `key`, and its className must stay byte-identical to the original.

Design-system accounting for this hunk:

| Class string | Where it already exists in this same file |
| --- | --- |
| `min-w-0` | Subscriptions row wrapper; Tickets row wrapper |
| `t-ui truncate text-ink-1` | Subscriptions (`s.msisdn`); Tickets (`t.subject`) |
| `t-caption truncate text-ink-4` | Subscriptions (`s.plan`); Tickets (`#{t.glpi_id}`) |
| `ml-auto flex items-center gap-sp-5` | unchanged, this row |
| `t-mono-l text-ink-1` | unchanged, this row |

**Zero new class strings.** The two-line cell is the file's own existing pattern, lifted from the sibling sections eight and forty lines away — not invented, and not imported from another file.

The `? ... : null` conditional form matches the file's existing style (`{customer.vip ? <Token strong>VIP</Token> : null}`).

Strict `!==` is sound here: both values originate from `Numeric(12, 2)` columns through `float()` and serialise as 2-decimal JSON numbers, so no epsilon comparison is warranted. Adding one would be arithmetic cruft.

**The import block is untouched** — `formatAmount`, `invoiceStatusKey` and `unpaidTotal` are all already imported by C-1's reordered list.

---

## §5 — Validation checklist

### 5.1 Gates

| # | Check | Command | Expected |
| --- | --- | --- | --- |
| 1 | Backend lint | `python -m ruff check apps/business-api/src/business_api/repositories.py` | All checks passed |
| 2 | Routes lint unchanged | `python -m ruff check apps/business-api/src/business_api/main.py` | **7 pre-existing** (I001 + 6× B904), count unmoved |
| 3 | Backend tests | `python -m pytest apps/business-api/tests -q` | **28 passed** (unchanged — see §5.5) |
| 4 | Typecheck | `node node_modules/typescript/bin/tsc --noEmit` | exit 0 |
| 5 | Lint | `npx eslint .` | 0 errors, **exactly 9** warnings |
| 6 | Format | `npx prettier --write` on the touched frontend files **only** | exit 0. Never `bun run format`. |
| 7 | Build | `npm run build` | exit 0 |
| 8 | Design system | `git diff -- Frontend/admin_dashboard/src/lib/nexus/status.ts` | empty |
| 9 | Deps | `git diff --stat -- Frontend/admin_dashboard/package.json` | empty |
| 10 | Router | `git diff -- Frontend/admin_dashboard/src/routeTree.gen.ts` | **no new hunk** beyond F18's `/notifications` |
| 11 | Query keys | `git diff -- Frontend/admin_dashboard/src/lib/nexus/query-keys.ts` | empty — no new key |
| 12 | Container | `docker compose -f infra/docker-compose/docker-compose.apps.yml build business-api && … up -d` | image rebuilt, healthy |

> **Gate wording, corrected.** Gates 8–11 are the only ones that can be literally empty. Gates on `apps/`, `src/`, and `routeTree.gen.ts` **cannot** be, because five features are uncommitted in this tree. FEATURE_20's results had to reinterpret two of its gates for exactly this reason. Each such gate above is therefore phrased as *"no new hunk beyond the known uncommitted set"*, and is verified by reading the specific hunks — not by expecting an empty diff.

**Container rebuild is required.** `apps/business-api/Dockerfile` bakes the source; a restart will not pick up the new key. This patch changes Python, so unlike FEATURE_20 it ends with a rebuild.

### 5.2 Backend correctness

| # | Check | Expected |
| --- | --- | --- |
| 13 | `git grep -c "i.invoice_number" -- apps/business-api/src/business_api/repositories.py` | 1 — the anchor was unique |
| 14 | `git grep -n "outstanding_amount" -- apps/business-api/` | exactly 1 hit, the new projection line |
| 15 | sqlalchemy import line unchanged | one line, `from sqlalchemy import func, or_, select` |
| 16 | `git diff -- apps/business-api/src/business_api/main.py` | **no new hunk** beyond the uncommitted F16/F17/F18 routes |
| 17 | `git diff --stat -- services/ infra/ packages/` | empty |
| 18 | No migration added | `packages/persistence/alembic/versions/` unchanged — the column already exists |

### 5.3 Frontend correctness

| # | Check | Expected |
| --- | --- | --- |
| 19 | `git grep -n "inv.amount" -- Frontend/admin_dashboard/src` | option A → 1 hit (the caption); option B/C → 0 |
| 20 | `git grep -n "i.amount" -- Frontend/admin_dashboard/src/lib/nexus/customer-view.ts` | 0 — the reducer was switched |
| 21 | `git grep -n "unpaidTotal" -- Frontend/admin_dashboard/src` | still exactly 3 — no rename happened |
| 22 | `git grep -n "outstandingTotal" -- Frontend/admin_dashboard/src` | still **0** — C-1's deletion was not resurrected |
| 23 | `git grep -n "Unpaid total" -- Frontend/admin_dashboard/src` | 1 — the footer label is unchanged by this feature |
| 24 | No new class strings | every class in the §4.4 hunk also appears elsewhere in `customer-detail.tsx` |
| 25 | No `rgb(` / `#hex` added | no hits in the diff |
| 26 | No `new Date(` / `toLocaleString(` / `getDay(` / `getHours(` added | no hits (pre-existing `formatAmount` untouched) |
| 27 | `t-caption truncate text-ink-4` renders only on differing rows | verified in §5.4 |

### 5.4 Live proof (the step that decides whether this was worth doing)

Use the row you captured in §0.3. Take its `customer_id`.

```bash
curl -s -H "X-Role: conseiller" \
  "http://localhost:8108/api/v1/customers/<CUSTOMER_ID>/360" | python -m json.tool
```

| # | Case | Expected |
| --- | --- | --- |
| 28 | Happy path | **200**; every `open_invoices[]` entry now carries `outstanding` |
| 29 | Values match the DB | each `outstanding` equals the `outstanding_amount` from §0.3, to 2dp |
| 30 | Role gate, one rank below | `X-Role: agent` → **403** `{"detail":"requires role >= conseiller"}` |
| 31 | Unknown customer | `/api/v1/customers/00000000-0000-0000-0000-000000000000/360` → **404**, unchanged |
| 32 | Malformed UUID | `/api/v1/customers/not-a-uuid/360` → **404**, not 500 (the D2 guard; H-5 was withdrawn) |

> Item 30 uses **`agent`**, the rank below `conseiller` — matching FEATURE_16 and FEATURE_17. FEATURE_18 used `conseiller` because its route was `superviseur`. Pick the rank below *this* route's role, not the rank a previous cookbook used.

Then in the UI: `/customers` → open the 360 modal for that customer.

| # | Case | Expected |
| --- | --- | --- |
| 33 | A row where `delta <> 0` | primary figure is the **remaining balance**; caption reads `Invoiced <face value>` |
| 34 | A row where `delta = 0` | **no caption**; renders exactly as before |
| 35 | Footer | `Unpaid total` equals the sum of the primary figures on the visible owed rows |
| 36 | Empty case | `Nothing outstanding.` unchanged |
| 37 | Chips | every `StatusChip` still non-blank across the 7 invoice statuses |

**If §0.3 put you in the all-`delta = 0` world, items 33 and 35 are latent passes.** Record them as such. Do not report a moved number that did not move.

### 5.5 Test note

**No test file is added, and `pytest` stays at 28.** This breaks the F16/F17/F18 rhythm deliberately, and the reason is worth stating rather than quietly skipping:

A contract test that proves the new key requires inserting a `Customer` **and** a `billing.Account` **and** a `billing.Invoice`. From the model file, the non-defaulted columns alone are:

- `Account`: `customer_id`, `account_number` (unique), `billing_cycle_day` (CHECK 1–28)
- `Invoice`: `account_id`, `customer_id`, `invoice_number` (unique), `period_start`, `period_end`, `issue_date`, `due_date`
- `Customer`: `national_id` is `nullable=False` — the FEATURE_16 lesson — plus whatever else `crm.py` requires

That is a three-table fixture whose full NOT NULL surface I have **not** enumerated from `crm.py`. Writing it from a partial reading is exactly the class of guess that produced the FEATURE_17 §4 defects. §6-C offers the two honest ways forward; until one is chosen, the live curl in §5.4 **is** the proof, and it is a stronger one than a synthetic fixture because it runs against real rows.

---

## §6 — Decisions needed before or during apply

### §6-A — How should the rows present the two numbers? *(decide before §4.4)*

| Option | Behaviour | Files | Trade-off |
| --- | --- | --- | --- |
| **A — row caption when differing** *(recommended)* | Row shows remaining balance; `Invoiced <face>` caption only when they differ | 4 | Rows sum to the footer. Face value stays visible. Reuses the file's own two-line pattern. Slightly more markup. |
| **B — footer only** | Footer sums `outstanding`; rows keep printing `amount` | 3 | Smallest diff, but the visible rows no longer add up to the visible total. Trades one arithmetic lie for another. |
| **C — rows switch silently** | Rows and footer both show `outstanding`; face value never shown | 3 | Ties out, smallest markup change. Face value disappears from the UI entirely. |

Recommendation **A**: it is the only option where what the operator reads is both true and self-consistent.

### §6-B — Should the caption say `Invoiced` or something else?

Proposed: `Invoiced {formatAmount(inv.amount)}`. Alternatives: `Face value …`, `of … invoiced`, `Original …`. `Invoiced` is preferred because it is the plain word for the number and it does not reuse the string `Total invoiced`, which C-1 just removed from the codebase.

### §6-C — Test coverage, given §5.5

| Option | What it costs | What it buys |
| --- | --- | --- |
| **C1 — no test** *(recommended for now)* | nothing; pytest stays 28 | Live curl proof against real rows. Consistent with FEATURE_20, which also added none. |
| **C2 — full fixture test** | read `crm.py` first, then a 3-table fixture; pytest → 29 | A durable regression guard on the key. Correct, but a separate small cookbook — I will not write the fixture without reading `crm.Customer` end to end. |
| **C3 — data-dependent test** | small | Fragile and a **new pattern** for this suite (skips when the DB is empty). Flagged, not recommended. |

### §6-D — Comment verbosity on the Python side

§4.1 puts a three-line comment above the new key. The C13 keys on `escalations()` carry a single line. If you prefer the terser house form, collapse it to `# FEATURE_21 — additive key (C13 precedent); `outstanding` is the balance still owed.` and drop the other two lines. Purely cosmetic; no gate depends on it.

### §6-E — Related defect found while reading, NOT built

`agent_activity()` counts `func.count(Turn.id)` grouped by `Turn.active_agent` with **no `speaker` predicate**. Your own §6-D grep on FEATURE_20 established that the CHECK constraint `speaker IN ('caller','agent')` permits agent turns while the writer only ever emits `caller`.

So FEATURE_20 / C-2's new label, **"Caller turns"**, is true *because of a property of the writer, not a property of the query*. The moment anything writes `speaker="agent"` — which the schema explicitly allows — the label silently becomes wrong and the metric silently starts double-counting.

A one-line `.where(Turn.speaker == "caller")` would make the query enforce what the label claims. It is **backend logic modification**, so under constraint 2 I am flagging it, not building it. Candidate **FEATURE_22** on request.

### §6-F — Numbering

`FEATURE_19` remains reserved and unbuilt (notification failure-reason capture: new column + Alembic migration + `_persist` change inside locked `packages/persistence`). This is `FEATURE_21`. Confirm if you would rather renumber.

---


FEATURE_20 is closed. The next cookbook — FEATURE_21_outstanding_amount.md — is above.
The four deviations were all mine
§5.2 #11 — outstandingTotal pre-count was 3, not 2. I had the import block from customer-detail.tsx verbatim in front of me and still wrote the count as definition + call site. The import line was on screen. That's a careless read of my own source material, not an ambiguity in the tree.
§5.3 #23 — the grep could never return 0. I specified a case-insensitive search for attributed across Frontend/ and asserted zero hits, when calls.tsx:255 carries "Speaker-attributed and PII-masked at capture." — a pre-existing transcript caption. Your reading was the correct one: three turns-metric occurrences, gone; one unrelated string, untouched. The check should have been scoped to "Attributed turns", which is what item 22 already did properly.
§5.1 #5 and #10 — gates written for a clean tree. FEATURE_20 was the first cookbook applied on top of four uncommitted features, and I wrote apps/ and routeTree.gen.ts as must be empty when they structurally could not be. Your reinterpretation — empty of this feature's contribution, verified by inspecting the specific hunks — is the only correct reading. F21 §5.1 now carries that wording natively, with an explicit note distinguishing the four gates that genuinely can be empty (status.ts, package.json, query-keys.ts, migrations) from the ones that can't.
Your §6-D grep found more than it was asked to
The instruction was confirm the writer only emits caller. You confirmed that — single call site at base_agent.py:181-184, no other callers — and then surfaced something I hadn't asked about: conversation.py:67 CHECKs speaker IN ('caller','agent').
So the schema deliberately anticipates agent turns that nothing ever writes. Which means C-2's new label is true because of a property of the writer, not a property of the query — agent_activity() has no speaker predicate at all. The first time anything writes speaker="agent", "Caller turns" becomes wrong and the metric silently starts counting both sides. A one-line .where(Turn.speaker == "caller") would make the query enforce what the label claims, but that's backend logic under constraint 2, so it's filed as §6-E — candidate FEATURE_22, flagged not built.
FEATURE_21, and the thing to run before you touch a file
Three files, four with the row treatment. Backend is a single additive key on customer_360's projection, with the C13 precedent; customers.server.ts gains one typed field with the same JSDoc form escalations.server.ts uses for its C13 keys; unpaidTotal switches which field it sums, keeping its name and keeping OWED_STATUSES exactly as C-1 left it.
§0.3 is the important section. Run the delta SQL first:
SELECT i.invoice_number, i.status, i.total_amount, i.outstanding_amount,
       (i.total_amount - i.outstanding_amount) AS delta
FROM billing.invoices i ORDER BY i.status;
​
If every delta is 0, this patch is correct and invisible — the same latent pass C-1 hit at item 19 — and the results should say so rather than report a number that didn't move. Worth noting in advance: a partial invoice with delta = 0 is a data inconsistency in its own right, since the status claims part-payment while the balance says none was made.
Two smaller notes. Reading customers.server.ts confirmed the F18 №4 rule a third time — getCustomer360 uses the raw: unknown validator, not zod, so F21 leaves it alone; clone the sibling you're editing. And unlike F20, this one does end in a rebuild, since the Dockerfile bakes the source.
§0.1 assumes C-1 is applied, and §0.2 explicitly forbids byte-matching FEATURE_20's customer-view.ts text — your gate #3 recorded prettier reformatting it, so that edit is specified as two token substitutions instead of a block replacement.
Open questions are §6-A (row presentation — recommend showing the face value as a caption only when it differs, so rows still sum to the footer), §6-C (no test, with the honest reason: a real contract test needs a three-table fixture and I haven't read crm.Customer's full NOT NULL surface), and §6-E above.



## §7 — Rollback

Three or four surgical reverts, in any order:

1. `repositories.py` — delete the `"outstanding"` line and its comment; recollapse the dict to one line.
2. `customers.server.ts` — delete the `outstanding` field and its JSDoc.
3. `customer-view.ts` — swap `i.outstanding` → `i.amount` and the parameter type back; restore the C-1 JSDoc sentence.
4. *(option A only)* `customer-detail.tsx` — restore the two spans from §4.4's `oldStr`.

Then `docker compose build business-api && up -d`. No migration to unwind, no data written, no route removed.

---

## §8 — Honest caveats

- **This may be a latent pass.** §0.3 decides. If no invoice has a non-zero delta, the patch is correct and invisible, and the results report must say so.
- **`amount` stays on the wire and stays slightly misleading in isolation.** It is the face value under a generic name. Renaming it to `face_value` would be truthful but is a **breaking** change to an existing key, which the C13 precedent does not sanction. The JSDoc in §4.2 is the mitigation.
- **A `partial` invoice with `delta = 0` is a data inconsistency**, not a code defect — status says part-paid, balance says otherwise. If §0.3 shows one, report it; do not patch around it.
- **`git grep`, not `rg`** — `rg` is absent from the operator's PATH.
- **GitHub cannot see this tree.** `version_81` on the remote is still `2f10a07`; F15–F18 and F20 are local and uncommitted. Every anchor in §4 was read from the remote and then adjusted for the known C-1 delta, which is why §0.1 exists.
