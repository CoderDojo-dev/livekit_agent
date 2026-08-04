# Runbook v2 — Corrections from live-system answers (2026-08-04)

**Supersedes:** `MASTER_APPLY_RUNBOOK.md` §0, §2, §4, §5 and the code blocks named below.
**Source:** your `answers.md`, executed against local `version_80` (HEAD `eda5f58`), 21 containers up.
**Rule:** where this file and any cookbook disagree, **this file wins.**

Nine recorded facts were wrong. Two of them would have broken the build on the first apply. One hazard I raised does not exist. One I raised is worse than I described — you proved it.

---

## §1. BUILD-BREAKING — primitive signatures do not match my cookbook code

This is the most important finding in your whole file, and it is my error. Your `B7` dump of `primitives.tsx` shows the **real** signatures:

```ts
EmptyState  ({ icon: Icon, title, description })                        // L368  ✓ matches
TableShell  ({ toolbar?, head, children, footer? })                     // L390  ✓ matches
Th          ({ children?, className?, align?: "left"|"right"|"center" })// L421
Td          ({ children?, className?, align? })                         // L446  ✗ NO colSpan
SearchInput ({ placeholder, className?, value?, onChange?: (v: string) => void }) // L471  ✗
Tabs        ({ items: string[], active, onSelect? })                    // L509  ✗
Segmented   ({ items: string[], active, onSelect?, className? })        // L544  ✗
```

My cookbooks were written against three assumptions that are all false. **These are global corrections — apply them to every remaining cookbook, not just the ones named.**

### G1 — `SearchInput.onChange` receives a **string**, not an event

Every cookbook that wired search did this:

```tsx
// WRONG — will not compile
onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
```

**Correct:**

```tsx
onChange={(v: string) => setSearch(v)}
```

**Affects:** C5, C6, C11, C14 — and any other page with a search box.

### G2 — `Tabs` / `Segmented` take `items: string[]` + `active: string` + `onSelect`, keyed by **label**

My code passed objects and `value`/`onChange`:

```tsx
// WRONG — will not compile
<Tabs items={CATALOG_TABS.map(t => ({ label: t.label, value: t.value }))}
      value={catalog} onChange={(v: string) => setCatalog(v as CatalogKind)} />
```

**Correct pattern** — keep a label↔key map, because the primitive only knows labels:

```tsx
const CATALOG_BY_LABEL: Record<string, CatalogKind> = {
  "Error messages": "errors",
  "Plans": "products",
  "Recharges": "recharges",
  "Geo areas": "areas",
};
const LABEL_BY_CATALOG: Record<CatalogKind, string> = {
  errors: "Error messages", products: "Plans",
  recharges: "Recharges", areas: "Geo areas",
};

<Tabs
  items={Object.keys(CATALOG_BY_LABEL)}
  active={LABEL_BY_CATALOG[catalog]}
  onSelect={(label: string) => {
    setCatalog(CATALOG_BY_LABEL[label]);
    setSearch("");
  }}
/>
```

**Affects:** C14 (`Tabs`), C11 (`Segmented`), C3 (`Segmented`, already applied — check it used the real shape), C5.

> This is the **same class of defect** that bit us in Feature 1, where `Segmented` was missing `type="button"`. I flagged "verify the real shape at apply time" in every cookbook, but I wrote the call sites against a guessed shape anyway. Your B7 dump is now the authority.

### G3 — `Td` does **not** accept `colSpan`

Every empty-state and error row in my cookbooks does this:

```tsx
// WRONG — colSpan is not in Td's signature
<Td colSpan={cols}><EmptyState … /></Td>
```

**Correct** — use a raw `<td>` for spanning cells only:

```tsx
<tr>
  <td colSpan={cols} className="px-sp-7 py-sp-8">
    <EmptyState icon={Library} title="…" description="…" />
  </td>
</tr>
```

**Also verify:** Feature 0's `TableErrorRow({ colSpan })` is already applied and Feature 1 passed 42/42 E2E with error states — so it must already render a raw `<td>` internally. **Check before reusing it:**

```bash
grep -n 'TableErrorRow' -A 14 src/components/nexus/states.tsx
```

If it renders `<Td colSpan=…>`, it is silently dropping the attribute and every error row is malformed. **Affects:** C5, C6, C8, C9, C10, C11, C12, C13, C14.

---

## §2. The lint gate is dead — replace it

My runbook §5.2 freezes acceptance at **"exactly 36 problems."** Your B6:

```
bunx tsc --noEmit → CLEAN (exit 0)
bun run lint      → 2704 errors (all prettier/prettier) → exit 1
```

**36 was a Feature-1-era number and is now meaningless.** The Lovable template injected far more files. Critically: **all 2704 are `prettier/prettier` formatting/CRLF, zero type or logic errors**, and `tsc` is clean.

**Replacement gate — use this for all ten remaining cookbooks:**

```bash
# 1. Type safety is the real gate
bunx tsc --noEmit                       # MUST be exit 0

# 2. Record the count BEFORE the cookbook, compare AFTER
bun run lint 2>&1 | tail -1             # note the number

# 3. Non-prettier errors must be ZERO — this is the meaningful check
bun run lint 2>&1 | grep -v 'prettier/prettier' | grep -E 'error|warning' | head -20

# 4. Format only the files you touched, so your diff stays clean
bunx prettier --write <the files this cookbook adds/modifies>

# 5. Build
bun run build                           # MUST be exit 0
```

**Rule:** `tsc` clean + **zero new non-prettier findings** + build green. Do **not** run `bun run format` repo-wide — it would reformat thousands of untouched files and make every cookbook diff unreviewable.

---

## §3. Only TEN cookbooks remain, not twelve

Your Q0.1 resolved the numbering and found more applied than I recorded:

| Cookbook | My record | Truth |
|---|---|---|
| F0 substrate | applied | **applied** — `src/lib/api/` present |
| F1 advisors | applied | **applied** |
| F2 availability | applied | **applied** |
| **F3 callbacks** | *designed, unapplied* | **APPLIED** — and maintained across v71–v79 |
| **F4 call logs** | *designed, unapplied* | **APPLIED** — `calls.tsx`, `patch-feature4-…-results.md`, F1–F4 methods in `repositories.py` |

**Remaining: 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 — ten.**

Two consequences:

1. **The C-1 correction is now moot for applying**, but I still need to know what F4 actually shipped: it was applied *with* my wrong null-guard advice in hand. Your A1 proves `max_frustration_score` has **0 NULLs**, so if the guard was applied it is dead code, not a bug. Check with `grep -n 'max_frustration' apps/business-api/src/business_api/repositories.py`.
2. **`/sessions` route ordering already happened.** My §3.1 warned that C4's `GET /api/v1/sessions` must precede `/sessions/{session_id}`. That apply is done — **verify it landed in the right order**, because a wrong order is a live bug right now:

```bash
grep -n 'api/v1/sessions' apps/business-api/src/business_api/main.py
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Role: conseiller' localhost:8108/api/v1/sessions
```

Expect the bare `/sessions` line **above** `/sessions/{session_id}`, and a 200.

---

## §4. Hazard register — revised

### H-1 retention floor — **CONFIRMED WORSE THAN I DESCRIBED. Approved.**

You proved it live:

```
POST /api/v1/jobs/retention?retention_days=-5&dry_run=true → 200
{"cutoff":"2026-08-09T06:36:38Z","sessions_matched":129,…}
```

A **negative** value produced a cutoff **in the future** and matched **every session in the database**. With `dry_run=false` that is total transcript destruction. Clamp approved — ship it **before** C10:

```python
# apps/business-api/src/business_api/main.py, in the retention route
if retention_days < 30:
    raise HTTPException(status_code=422, detail="retention_days must be >= 30")
```

Put it in the **route**, not the job, so both the clamp and the 422 are visible at the API boundary.

### H-5 UUID guard — **WITHDRAWN. I was wrong.**

```
GET /api/v1/customers/not-a-uuid/360 → 404   (not 500)
```

`to_uuid()` returns `None` for a malformed id → `customer is None` → 404. The guard already exists. **Remove H-5 from the register and drop the C11 amendment.**

### H-4 internal key — **ACTIVE, and that is good news**

`INTERNAL_API_KEY` is **set** locally (`dev-key-123`). So C6 will exercise the key-gated branch on your machine instead of passing locally and 403-ing later. Ensure C6's server-side calls send `X-API-Key`.

### H-2 `advisor_shifts` — **31 rows, not 33**

My record says the reconstruction produced 33. Yours reads **31**. A 2-row gap I cannot explain from here. **Do not TRUNCATE or rebuild.** Diff against the v73 audit before touching anything; if the 2 rows were reconstruction artifacts, 31 is correct and my record is simply stale.

---

## §5. Data facts that change cookbook content

### F5.1 — `audit.audit_ledger`, not `audit_ledger_entries`

My questionnaire and C10 use the wrong table name. **Correct it in C10** before applying, or the query fails outright. (Reassuringly loud: a wrong table name errors, it does not silently return nothing.)

### F5.2 — `execution.action_ledger` is **empty (0 rows)**

C8's failed-actions view will render its empty state permanently until an action runs. That is correct behaviour, not a bug — but **test C8 against the empty state**, since that is the only state you can currently observe.

### F5.3 — `verdict` values are **UPPERCASE**

`AUTHORIZED` / `REFUSED` / `ESCALATE`. Chip mapping is **case-sensitive** and `StatusChip` returns `null` for an unmapped key — an invisible cell, not an error. C8's mapping must lower-case or map the uppercase literals explicitly. **This is the blank-chip trap, thirteenth recurrence.**

### F5.4 — `final_disposition` is **NULL on all 129 sessions**

So F4's `NULL → in_progress` mapping is not an edge case, it is **the only case**. No `resolved`/`escalated`/`dropped` exists in real data. C9's KPIs reflect this: `resolved: 0`, `escalated: 0`, `containment_rate: 0.0`. **C9 must not read all-zero KPIs as a bug** — they are arithmetically correct on data where no session has a disposition.

### F5.5 — invoices have `overdue` and `partial`, no `paid`

C11 mapped `partial → in_progress`, `overdue → overdue`. Both present, both mapped. Good — but seed a `paid` row before trusting that path.

### F5.6 — escalations: 58/58 open, `target` is always `manager_agent`

Four triggers observed: `hard_failure`, `abuse`, `clarify_fail`, `identity_fail`. **`human_advisor` never occurs** — so C13's target rendering has one real value, and the `human_advisor` path is untested by data. Keep the mapping; do not present it as observed.

### F5.7 — no `turn_index` gaps anywhere

My C13 B12 claimed dropped writes make transcript holes normal. **The data does not support it** — `count(turns) == max(turn_index)` for every session. The dropped-write path exists in `writer.py` but has evidently never fired here. **Soften that claim in C13/C4**: gaps are *possible by design*, not *observed*.

### F5.8 — no port collision

My Phase 1 note that `ocs-billing-sim` and `nms-sim` collide on 8107/8108 was wrong: those are **container-internal** ports, mapped to hosts 8109/8110. **Withdrawn.**

---

## §6. Decisions recorded

| # | Decision | Action |
|---|---|---|
| D1 | 30-day floor + 422 | **ship before C10** (route-level) |
| D2 | UUID guard | **already exists** — H-5 withdrawn |
| D3 | errors/products/recharges → `superviseur`; `areas` → `administrateur` | **C14 §2.3 rewritten** — split into two role gates |
| D4 | `/policies` → `superviseur` read-only | recorded |
| D5 | shared credential OK for dev; scope multi-user before leaving your machine | recorded |
| D6 | C9 ships without fabricated health; real probes = separate cookbook | recorded |
| D7 | add `created_at` + `customer_id` to `/escalations` | **C13 gains +2 dict keys** — no longer 0-backend |
| D8 | nothing closes an escalation | see §7 — **needs one more decision** |
| D9 | `/rules` is filler; slot → `/reference` | confirmed |
| D10 | four unexposed tables out of scope | recorded |
| D11 | callback lifecycle fields **already exposed** by `to_dict()` | amendment withdrawn; any gap is UI-only |
| D12 | `updated_at` = deliberate migration | recorded, not in C14 |
| D13 | policy-service and business-api share `../../.env` | **document the invariant** |
| D14 | drop "Handled" | confirmed |

### C14 §2.3 replacement (per D3)

```python
_SUPERVISOR_CATALOGS = {"errors", "products", "recharges"}

@app.get("/api/v1/reference/catalogs/{catalog}")
def reference_catalog(
    catalog: str,
    db: DbSession,
    role: AdministrateurRole | None = None,   # see note
    search: str = "",
    limit: int = 200,
):
    ...
```

**Note — do not guess this one.** `require_role` is a *factory* returning a dependency, so a single handler cannot vary its required rank at runtime. Two clean options:

- **(a) two routes** — `/reference/catalogs/{catalog}` gated `superviseur` for the three soft catalogs, and a separate `/reference/geo-areas` gated `administrateur`. Explicit, no cleverness.
- **(b) one route** gated `superviseur`, with an in-handler rank check for `areas` using `ROLE_RANK`.

**I recommend (a)** — it keeps the gate declarative and visible in the route table, consistent with every other route in `main.py`. Confirm and I will rewrite C14 §2.3 accordingly.

---

## §7. Two things I still need from you

### Q1 — Where does an escalation get closed? (blocks C13)

58/58 open, and **no code path writes `resolution`**. My C13 ships a read-only page with a decorative filter. Your D8 recommends a supervisor workflow transition — which is a **write path**, i.e. new business logic that Constraint 3 forbids me from inventing.

**Pick one:**
- **(a)** C13 stays read-only now; closing is scoped later as its own cookbook. *(safest, keeps Constraint 3 intact)*
- **(b)** I scope a minimal `PATCH /api/v1/escalations/{id}` with the four allowed `resolution` values + audit-ledger entry, as its own cookbook after the three batches.
- **(c)** Closing belongs in `apps/supervisor-dashboard`, not the admin console — I document it and leave it alone.

### Q2 — Which action was in flight when the agent went silent? (blocks Phase 2 closure)

Your C3 read is the most valuable thing in the file for this. `ticket_tools.py`'s `_mcp_call()` does async MCP I/O over `httpx` **without `context.foreground()`** — unlike `guards.ensure_identity_verified`, which my patch wraps. So **my patch is very likely incomplete**: it fixes the identity gate, and the six ticket tools have the same shape.

Your own reasoning — *"d'accord je vais vérifier ça"* implies a **read** tool, most likely `check_customer_tickets` or `get_ticket_state` — matches mine. But I will not extend a patch to six more tools on inference.

**Tell me which one it was:** checking a **bill/invoice**, a **plan**, an **outage**, **existing tickets**, or **identity/CIN verification**. One word is enough. `livekit-agents` is confirmed at **1.6.5**, so the fix location is stable either way — E1 is closed.

---

## §8. Revised apply plan (your option **b**, three batches)

Adjusted for the two already-applied cookbooks, the new gate, and D7 moving C13 off zero-backend.

**Before batch 1 — two prerequisites, ~10 minutes:**
1. Ship the **D1 retention clamp** (route-level, 422).
2. Run the **G3 check** on `TableErrorRow` — it determines whether every error row in all ten cookbooks is malformed.

| Batch | Cookbooks | Backend | Notes |
|---|---|---|---|
| **1** | C5 Tickets · C6 Knowledge/RAG · C7 Guardrails · **C13 Escalations** | C13 only (**+2 dict keys**, D7) | C13 must delete the ingestion panel **before** `INGESTED_FILES` is removed (B9 — it is still imported today) |
| **2** | **C9 KPIs first** · C8 Decisions · C14 Reference | +2 each | **C9 first is non-negotiable** — `delta?` unblocks batch 3. C8 needs the uppercase-verdict fix (F5.3); C14 needs the D3 role split |
| **3** | C10 Audit · C11 Customers · C12 Agents | +2 each | C10 with the **`audit_ledger`** name fix (F5.1) + `formatInteger` fix (C-2) |

One commit per cookbook **inside** each batch, so intra-batch bisect survives. Apply G1/G2/G3 to every cookbook as you go.

**On F2 — agreed, and I'll do it your way:** per batch, a flat `git apply`-able diff **plus** a `gate.md`, *in addition to* the cookbooks. The diff carries the route-ordering comments and expected greps inline, so the mechanical path never loses the constraints that matter.

---

## §9. Still open, unchanged

- **C12 "Attributed turns" is confirmed broken as labelled.** Your C1 + A8 prove `record_turn` is only ever called with `speaker="caller"` — agent turns are **never persisted**. All five personas appear, but only on caller turns. So the metric counts **half the conversation**. Fix the label ("Caller turns handled"), or add agent-turn writing — which is a worker change, not a dashboard change. **I recommend relabelling in C12 and flagging the write gap separately.**
- `STRICT_PERSONA_CONTRACT` unset → persona violations degrade to `logger.error`. C12's CI-only recommendation stands.
- `formatPercent` is confirmed **0–1** (`Intl` percent style). C9's separate `formatRatio` was the right call; `formatDelta` takes 0–100 — do not mix them.
- D13 invariant to write into deploy docs: **`policy-service` and `business-api` must read the same `POLICY_*` file**, or `/policies` silently displays thresholds that differ from those enforced.
