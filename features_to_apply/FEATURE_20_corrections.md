# FEATURE_20 — Truth-in-labelling: unpaid total, caller turns, and the POLICY_* deployment invariant

> Branch of truth: `version_81` (GitHub head `2f10a07`). Operator's local HEAD carries F15 + F16 + F17 + F18, uncommitted.
> Every line quoted below was read from `version_81` in this session. SHAs are given per file so you can diff against what I actually saw.

---

## §0. Numbering, and why three items are in one cookbook

**Numbering.** Operator decision F18 §6-D reserved **FEATURE_19** for *notification failure-reason capture* (flagged, not built — it needs a new column, an Alembic migration, and a `_persist` change inside locked `packages/persistence`). FEATURE_19 therefore stays parked and unbuilt. This cookbook is **FEATURE_20**.

**Why one document.** The standing rule is *one feature, one cookbook*. These three items are **not features** — they are corrections, and each is between one and five lines:

| # | Item | Origin | Files | Net lines |
| --- | --- | --- | --- | --- |
| **C-1** | `"Total invoiced"` is not the total invoiced | F16 backlog | 2 frontend | ~14 |
| **C-2** | `"Attributed turns"` counts caller turns | C12 backlog | 2 frontend | 5 |
| **C-3** | `POLICY_*` co-location is undocumented (D13) | Runbook D13 | 1 new doc | new file |

The tree already has a precedent for bundling corrections rather than splitting them: **`features_to_apply/RUNBOOK_V2_CORRECTIONS.md`** collects G1/G2/G3 in one file. Features are split; corrections are bundled. This follows that convention.

**They are independently appliable.** C-1, C-2 and C-3 touch four disjoint files. Apply any subset, in any order, and revert any one without touching the others. §5 gives a separate gate block per item.

**No backend Python is touched by any of the three.** Consequences, which differ from F16/F17/F18:

- `pytest` baseline stays at **28**. No new test, because nothing testable changed on the server.
- **No `docker compose build business-api`.** There is no new route and no repository change. This is the first cookbook in the 15–20 series that ends *without* a container rebuild.
- **`routeTree.gen.ts` is NOT regenerated.** No route is added. If it appears in your diff, something else did it.

**Pre-applied conventions.** All six FEATURE_17 adaptations are already honoured below, plus the two F18 ones. Nothing here uses `self.session`, `dict[str, Any]`, `_: Role`, a `raw: unknown` validator where the sibling uses zod, a bare `formatInstant`, or `>= CAP` cap captions — because nothing here touches the backend, a server function, or a cap caption at all. G1/G2/G3 are untouched: no `SearchInput`, no `Tabs`/`Segmented` signature change, no `Td colSpan`.

---

## §1. Feature name & scope

**Name.** Truth-in-labelling corrections + the D13 deployment invariant.

**In scope.**

1. **C-1** — the customer 360 modal's invoice summary line claims `"Total invoiced"`. It is not. Relabel it, and stop summing invoices that nobody owes.
2. **C-2** — the `/agents` page calls its volume metric `"Attributed turns"`. It counts rows in `conversation.turns`, every one of which is (per the C12 finding) a **caller** utterance. Relabel.
3. **C-3** — `business-api` and `policy-service` must read the **same** `POLICY_*` values or the governance registry lies to the supervisor. Locally they agree only because one `.env` file is mounted into both containers. Nothing states this, and nothing enforces it. Write it down.

**Out of scope, deliberately.** Exposing `Invoice.outstanding_amount` (§6-B), correcting `customer_360`'s `!= "paid"` filter (§6-C, backend core logic — locked), mirroring the two unmirrored `POLICY_*` thresholds into the governance registry (§6-E), and FEATURE_19.

---

## §2. Backend reference (read-only — nothing here is modified)

### 2.1 What `customer_360` actually returns

`apps/business-api/src/business_api/repositories.py` — SHA `b9954b539de21e7b8418fe10ea7e0c77493ecd84`:

```python
"open_invoices": [
    {"invoice": i.invoice_number, "amount": float(i.total_amount), "status": i.status}
    for i in invoices if i.status != "paid"
],
```

Three facts follow, and all three matter:

1. **The list excludes paid invoices.** So a total computed over it can never be "total invoiced".
2. **`amount` is `Invoice.total_amount`** — the invoice's face value — **not `Invoice.outstanding_amount`.**
3. **The filter is `!= "paid"`, not a whitelist.** The CHECK constraint on the column is:

```python
CheckConstraint(
    "status IN ('draft','issued','paid','partial','overdue','disputed','void')", name="status"
)
```

`!= "paid"` therefore also admits **`draft`** (never issued to the customer) and **`void`** (cancelled). Both are currently being added into a number rendered as money, under a section captioned *"Nothing outstanding."* when empty.

### 2.2 Both columns exist; only one is exposed

`packages/persistence/src/persistence/models/billing.py` — SHA `2ce40c1f43696bde1602f59023c593767cffcb2f`:

```python
total_amount:       Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
outstanding_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
status:             Mapped[str]   = mapped_column(String(20), nullable=False, server_default=text("'issued'"), index=True)
```

Both are `nullable=False`. `status` is `nullable=False`, which is why the helper in §4.1 can declare it non-optional.

For a `partial` invoice the two amounts differ by construction — that is what `partial` means. **The recorded live-data fact for this database is that invoices carry `overdue` and `partial` statuses and no `paid` at all.** So the face-value/outstanding gap is not hypothetical here; it is present today. That is §6-B.

### 2.3 What `agent_activity` actually counts

Same file:

```python
rows = self._s.execute(
    select(
        Turn.active_agent.label("agent"),
        func.count(Turn.id).label("turn_count"),
        func.count(func.distinct(Turn.session_id)).label("session_count"),
        func.max(CallSession.start_time).label("last_seen"),
    )
    .join(CallSession, CallSession.id == Turn.session_id)
    .where(CallSession.start_time >= since)
    .where(Turn.active_agent.isnot(None))
    .where(Turn.active_agent != "")
    .group_by(Turn.active_agent)
    .order_by(func.count(Turn.id).desc())
).all()
```

It is `count(Turn.id)` grouped by `active_agent`. **There is no `speaker` predicate.** So the metric is "transcript turns recorded while this persona held the floor". If — per the C12 finding — the writer only ever emits `speaker="caller"`, then every one of those turns is a caller utterance, and the metric measures **inbound volume**, not persona output. See §6-D: this is the one claim in this cookbook I could not verify from the branch, and I am not asserting it.

`total_turns` is `sum(a["turns"] for a in agents)` over the same rows.

### 2.4 The D13 invariant, in the code's own words

`apps/business-api/src/business_api/policy_view.py` — SHA `5f725f460ed688bac7cbd76c96a02b02ab336677`, module docstring:

> The deterministic policy engine (policy-service) is twelve-factor: it reads its numeric thresholds from `POLICY_*` environment variables, never from a table. […] This module removes that drift by construction: the business-api reads the SAME `POLICY_*` env the engine reads (**both containers load the same `.env` via `env_file`**) and overlays the live enforced numbers onto each governed rule at read time. […] The defaults below MUST match `policy_service.config.PolicyThresholds`. `tests/test_policy_view.py` pins them so the two cannot silently diverge.

So the module *knows* the invariant. What is missing is that the invariant is stated only inside one Python docstring — where nobody deploying the system will read it.

**The enforcer**, `services/policy-service/src/policy_service/config.py` (SHA `b1e05db27deca5d4300461c80d50c8041c19fa2f`):

```python
payment_cap:               float          = Field(200.0,  alias="POLICY_PAYMENT_CAP_TND")
deferral_min_age_days:     int            = Field(180,    alias="POLICY_DEFERRAL_MIN_AGE_DAYS")
deferral_max_per_year:     int            = Field(2,      alias="POLICY_DEFERRAL_MAX_PER_YEAR")
deferral_unpaid_threshold: float          = Field(150.0,  alias="POLICY_DEFERRAL_UNPAID_THRESHOLD_TND")
topup_denominations: tuple[float, ...]    = Field((5.0, 10.0, 20.0, 50.0), alias="POLICY_TOPUP_DENOMINATIONS_TND")
plan_codes:          tuple[str, ...]      = Field((),     alias="POLICY_PLAN_CODES")
```

**The reader**, `policy_view.py`:

```python
_DEFAULTS = {
    _PAYMENT_CAP_ENV:            200.0,
    _DEFERRAL_MIN_AGE_ENV:       180,
    _DEFERRAL_MAX_PER_YEAR_ENV:  2,
    _DEFERRAL_UNPAID_ENV:        150.0,
}
```

Four of six. `POLICY_TOPUP_DENOMINATIONS_TND` and `POLICY_PLAN_CODES` are **enforced by the engine but invisible in the governance registry** — a supervisor reviewing `/policies` cannot see them at all. That is a real gap; it is §6-E, flagged not fixed.

**Why they agree today**, `infra/docker-compose/docker-compose.apps.yml` (SHA `6b3cb641789c92858bec728382296e6464ed9573`):

```yaml
  policy-service:
    env_file: [../../.env]
    environment:
      DATABASE_URL: "..."
  business-api:
    env_file: [../../.env]
    environment:
      DATABASE_URL: "..."
      MINIO_ENDPOINT: "minio:9000"
```

Neither `environment:` block sets any `POLICY_*`. Both inherit the same single file. **They agree because there is exactly one file — not because anything checks.** And `deploy/helm/` and `infra/helm/` both exist in the tree, which is precisely the topology where that one-file guarantee stops holding: each chart gets its own ConfigMap.

---

## §3. Endpoints

**None.** No endpoint is added, changed, or removed. No CORS hunk. No middleware. `apps/business-api/` is not touched by this cookbook at all.

This is the whole point of C-1: the correct fix for a false label is not a new endpoint, it is a true label.

---

## §4. Implementation plan

### C-1 — `"Total invoiced"` → `"Unpaid total"`

#### 4.1 `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts`

**Current** (SHA `a3e528655426b39364f9c3b8c6bcc6ef1f83bfd6`, final block of the file):

```ts
/** Sum of open invoice amounts, for the panel's summary line. */
export function outstandingTotal(invoices: Array<{ amount: number }>): number {
  return invoices.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
}
```

The name is the second lie. It says `outstanding`; it sums `total_amount`. Nothing in this function has ever touched `Invoice.outstanding_amount`.

**Replace the entire block with:**

```ts
/**
 * Invoice statuses that represent money someone still owes.
 *
 * `customer_360` returns every invoice whose status is not `paid` (repositories.py,
 * `open_invoices`), which sweeps in `draft` (never issued to the customer) and `void`
 * (cancelled). Neither is owed by anybody, so neither belongs in a money total.
 */
const OWED_STATUSES = new Set<string>(["issued", "partial", "overdue", "disputed"]);

/**
 * Sum of the invoices that still represent money owed, for the panel's summary line.
 *
 * Two deliberate narrowings against the raw payload:
 *  - `draft` and `void` rows stay VISIBLE in the list but are excluded from the total.
 *  - The figure is invoice FACE VALUE (`Invoice.total_amount`), because that is the only
 *    amount `customer_360` projects. `Invoice.outstanding_amount` exists and is not exposed,
 *    so a part-paid (`partial`) invoice contributes its full amount. See FEATURE_20 §6-B.
 */
export function unpaidTotal(invoices: Array<{ amount: number; status: string }>): number {
  return invoices.reduce(
    (sum, i) => (OWED_STATUSES.has(i.status?.toLowerCase() ?? "") ? sum + (Number(i.amount) || 0) : sum),
    0,
  );
}
```

**Provenance of every construct used.**

| Construct | Where it already exists in the tree |
| --- | --- |
| `new Set<string>([...])` module constant | `agent-view.ts` — `const BY_CLASS = new Map(...)`, and `const seen = new Set<string>()` inside `mergeAgentRows` |
| `status?.toLowerCase()` defensive read | `customer-view.ts` itself — `invoiceStatusKey` and `subscriptionStatusKey` both open with it |
| `Number(x) || 0` coercion | the function being replaced |
| `reduce` with a ternary accumulator | new shape, but `reduce` itself is the existing idiom here |

**On `?? ""`:** `status` is declared non-optional and `billing.invoices.status` is `nullable=False` (§2.2), so `?.` can never short-circuit. It is kept for symmetry with the two sibling functions in this same file, and `?? ""` guarantees `Set<string>.has()` receives a `string` under `strictNullChecks` — no `string | undefined`. This is the same class of type hole that FEATURE_17 adaptation #5 (`formatInstant`) hit; it is closed here at authoring time rather than at `tsc` time.

#### 4.2 `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx`

**Two edits.** SHA `ee6148edf70e825e02d4ed01433df220394181f4`.

**Edit 1 — the import.** The existing named-import list is strictly alphabetical, so `unpaidTotal` does not sit where `outstandingTotal` sat. Reorder as shown; do not just swap the word in place.

```diff
 import {
   customerStatusKey,
   formatAmount,
   invoiceStatusKey,
   languageLabel,
-  outstandingTotal,
   subscriptionStatusKey,
+  unpaidTotal,
 } from "@/lib/nexus/customer-view";
```

**Edit 2 — the summary line.** Inside the `Open invoices` section, the block immediately after the `</ul>`:

```diff
                 <div className="mt-sp-6 flex items-center border-t border-stroke-subtle pt-sp-5">
-                  <span className="t-label text-ink-3">Total invoiced</span>
+                  <span className="t-label text-ink-3">Unpaid total</span>
                   <span className="t-mono-l ml-auto text-ink-1">
-                    {formatAmount(outstandingTotal(query.data!.open_invoices))}
+                    {formatAmount(unpaidTotal(query.data!.open_invoices))}
                   </span>
                 </div>
```

**Zero class strings change.** `mt-sp-6 flex items-center border-t border-stroke-subtle pt-sp-5`, `t-label text-ink-3` and `t-mono-l ml-auto text-ink-1` are all preserved byte-for-byte. Nothing is added to the DOM. The design system is not touched — this patch changes two words and one function name.

**Type safety.** `unpaidTotal` now requires `status` on each element. The call site already passes `query.data!.open_invoices`, whose element type is used three lines above as `invoiceStatusKey(inv.status)` — so `status: string` is already on the wire type in `customers.server.ts` and already compiles. No wire-type edit is needed. `tsc` will confirm.

#### 4.3 Why `"Unpaid total"` and not something else

| Candidate | Verdict |
| --- | --- |
| `Total invoiced` (current) | **False.** Paid invoices are filtered out upstream. |
| `Outstanding` | **False.** The sum is face value, not `outstanding_amount`. Swapping one lie for another. |
| `Open invoices total` | True but redundant — the section header is already `Open invoices`. |
| **`Unpaid total`** | **True, once `draft`/`void` are excluded.** Every remaining status (`issued`, `partial`, `overdue`, `disputed`) is an invoice that has been issued and not settled. Two words, fits the `t-label` slot. |

The existing empty-state caption *"Nothing outstanding."* stays. With `draft`/`void` excluded from the total it is no longer contradicted, and it is accurate on its own terms: no unpaid invoices means nothing is outstanding.

---

### C-2 — `"Attributed turns"` → `"Caller turns"`

> **Run the §6-D verification before applying this one.** It is one `git grep`. If it comes back the way C12 recorded, apply the diffs below. If it does not, apply the fallback in §6-D instead. Both are written out in full; you are choosing between two finished patches, not filling in a blank.

#### 4.4 `Frontend/admin_dashboard/src/routes/agents.tsx`

SHA `cd36e1619276643f54c9c1a13c408e59376cf53d`. **Four edits.** Note that `Attributed turns` appears **twice** — do not use a blind find-and-replace on the file; each hunk below carries its own surrounding context.

**Edit 1 — the hero metric:**

```diff
         <HeroStat
-          label="Attributed turns"
+          label="Caller turns"
           value={formatInteger(totalTurns)}
           context={`Across ${days} days`}
         />
```

**Edit 2 — the idle card's context line:**

```diff
         <StatCard
           label="Idle in window"
           value={formatInteger(idle.length)}
-          context="No attributed turns"
+          context="No caller turns"
         />
```

**Edit 3 — the column header:**

```diff
               <Th>Persona</Th>
               <Th>Role in graph</Th>
-              <Th align="right">Attributed turns</Th>
+              <Th align="right">Caller turns</Th>
               <Th align="right">Share</Th>
```

**Edit 4 — the empty state:**

```diff
                 <EmptyState
                   icon={Bot}
                   title="No persona activity"
-                  description="No turns were attributed to a persona in this window."
+                  description="No caller turns were handled by a persona in this window."
                 />
```

#### 4.5 `Frontend/admin_dashboard/src/components/nexus/agent-detail.tsx`

SHA `9f85921044312fdb9d1d61cce41059ac2c16a814`. **One edit**, in the `Observed activity` grid:

```diff
             <div>
               <p className="t-mono-l text-ink-1">{formatInteger(row.turns)}</p>
-              <p className="t-caption text-ink-4">Attributed turns</p>
+              <p className="t-caption text-ink-4">Caller turns</p>
             </div>
             <div>
               <p className="t-mono-l text-ink-1">{sharePercent(row.turnShare)}</p>
               <p className="t-caption text-ink-4">Share of turns</p>
             </div>
```

**`"Share of turns"` is left alone.** It is a ratio of the same quantity to itself — relabelling it buys nothing and it is already neutral.

**Nothing else in C-2 changes.** No TypeScript identifiers move: `AgentRow.turns`, `turnShare`, `mergeAgentRows`, `sharePercent` and the `total_turns` wire field all keep their names. Only five display strings change. Five string literals, zero logic, zero classes.

---

### C-3 — D13: write the `POLICY_*` invariant into a deployment doc

#### 4.6 Where it goes, and why there

`docs/` contains exactly one entry — `versions/` — so there is no deployment guide to append to. `deploy/` contains `backup/ gateway/ helm/ otel/ postgres/ secrets/` and **no file at its root**.

**Create `deploy/README.md`.** It sits directly beside `helm/` and `secrets/` — the two surfaces that break the invariant — which is where someone about to break it will be standing.

**Note for the diff gate:** the standing check is `git diff --stat -- services/ infra/ packages/`. `deploy/` is not in that list, so this new file does not disturb it. It is also not Python, so `ruff` and `pytest` are unaffected.

#### 4.7 Full content of the new file

```markdown
# Deployment notes

Operational invariants that are enforced by nothing and must therefore be held by hand.
Each one is a rule that is currently satisfied *by accident* of the local topology.

---

## D13 — `policy-service` and `business-api` MUST read the same `POLICY_*` values

### The rule

The deterministic policy engine (`services/policy-service`) is twelve-factor: it reads every
numeric threshold from `POLICY_*` environment variables and never from a table. The admin
dashboard's rule registry (`/policies`) does **not** re-read those numbers from
`reference.business_rules` — that table is the governance record only. Instead
`apps/business-api/src/business_api/policy_view.py` reads the *same* `POLICY_*` variables and
overlays the live enforced values onto each governed rule at read time.

This is deliberate, and it is documented in that module's docstring: it removes registry drift
by construction. But it only works if **both processes see identical values**.

> If `policy-service` and `business-api` are given different `POLICY_*` values, `/policies`
> will confidently display a threshold that is not the one being enforced on live calls.
> There is no error, no warning, and no log line. The dashboard simply lies.

### The variables

Defined in `services/policy-service/src/policy_service/config.py` (`PolicyThresholds`):

| Variable | Default | Mirrored in `policy_view.py`? |
| --- | --- | --- |
| `POLICY_PAYMENT_CAP_TND` | `200.0` | yes |
| `POLICY_DEFERRAL_MIN_AGE_DAYS` | `180` | yes |
| `POLICY_DEFERRAL_MAX_PER_YEAR` | `2` | yes |
| `POLICY_DEFERRAL_UNPAID_THRESHOLD_TND` | `150.0` | yes |
| `POLICY_TOPUP_DENOMINATIONS_TND` | `5,10,20,50` | **no** |
| `POLICY_PLAN_CODES` | *(empty)* | **no** |

The last two are enforced by the engine but are not surfaced in the governance registry at all.
A supervisor reviewing `/policies` cannot see them. Tracked as FEATURE_20 §6-E.

### Why it holds today

`infra/docker-compose/docker-compose.apps.yml` gives both services `env_file: [../../.env]`, and
neither service's `environment:` block overrides any `POLICY_*`. They agree because there is
exactly one file — not because anything verifies it.

### Where it breaks

| Topology | Risk |
| --- | --- |
| Compose, as shipped | Safe. One `.env`, two consumers. |
| Compose with a per-service `environment:` override | **Broken** the moment a `POLICY_*` is set on one service only. |
| Helm / Kubernetes (`deploy/helm`, `infra/helm`) | **Broken by default.** Each chart carries its own ConfigMap/Secret. Nothing makes two charts share a value. |
| Host dev (`make dev` / honcho) | Safe. Both processes inherit one shell environment. |

### The rule to apply

1. Source every `POLICY_*` value from **one** place — a single ConfigMap, a single secret, a
   single `.env` — and mount that same place into **both** `policy-service` and `business-api`.
2. Never set a `POLICY_*` in a per-service `environment:` block or a per-chart `values.yaml`.
3. When adding a threshold, add it in three places or none:
   `PolicyThresholds` (enforcer) → `policy_view._DEFAULTS` + `GOVERNED_BY` (registry) →
   `tests/test_policy_view.py` (the pin that stops the two drifting).

### Verifying it after a deploy

```bash
# The two must print identical values.
docker compose exec policy-service env | grep '^POLICY_' | sort
docker compose exec business-api   env | grep '^POLICY_' | sort
```

On Kubernetes, substitute `kubectl exec deploy/<name> -- env`.

If the two lists differ, `/policies` is misreporting enforced policy. Fix the deployment, not
the dashboard.
```

---

## §5. Validation checklist

### 5.1 Gates (run once, after applying whichever subset you chose)

| # | Check | Command | Expected |
| --- | --- | --- | --- |
| 1 | Typecheck | `node node_modules\typescript\bin\tsc --noEmit` | exit 0 |
| 2 | Lint | `npx eslint .` | 0 errors, **exactly 9** warnings |
| 3 | Format | `npx prettier --write` on **touched files only** | exit 0 — never `bun run format` |
| 4 | Build | `npm run build` | exit 0 |
| 5 | Backend untouched | `git diff --stat -- apps/ services/ packages/ infra/` | **empty** |
| 6 | Tests unchanged | `python -m pytest apps/business-api/tests -q` | **28 passed** (unchanged) |
| 7 | No rebuild needed | *(none)* | do **not** rebuild `business-api` — no route changed |
| 8 | Design system | `git diff -- src/lib/nexus/status.ts` | empty |
| 9 | Dependencies | `git diff --stat -- package.json` | empty |
| 10 | Router | `git diff -- src/routeTree.gen.ts` | **empty** — no route was added |

### 5.2 C-1 specific

| # | Check | Expected |
| --- | --- | --- |
| 11 | `git grep -n "outstandingTotal"` | **0 hits** after the patch (2 before: definition + one call site) |
| 12 | `git grep -n "Total invoiced"` | **0 hits** |
| 13 | `git grep -n "unpaidTotal"` | exactly 3 (definition, import, call site) |
| 14 | `git diff --stat -- Frontend/admin_dashboard/src/` | exactly 2 files for C-1 |
| 15 | No new class strings | `git diff` shows no added `className` — verify by eye |
| 16 | No `rgb(` / `#hex` added | no hits |
| 17 | No `new Date(` / `toLocaleString(` / `getDay(` / `getHours(` added | no hits |
| 18 | Open a 360 modal with ≥1 unpaid invoice | summary line reads **Unpaid total**, chips unchanged, rows unchanged |
| 19 | Open a 360 modal with a `void` or `draft` invoice | the row is **still listed**, still chipped `archived`/`draft`, and is **not** in the total |
| 20 | Open a 360 modal with no invoices | `Nothing outstanding.` — unchanged |

**Item 19 is the one to actually look at.** If your seed has no `void`/`draft` rows the visible number will not move at all, and that is a pass, not a failure — it means the two defects were latent rather than active. Check with:

```sql
SELECT status, count(*) FROM billing.invoices GROUP BY status ORDER BY 2 DESC;
```

### 5.3 C-2 specific

| # | Check | Expected |
| --- | --- | --- |
| 21 | §6-D verification run **before** applying | see §6-D |
| 22 | `git grep -n "Attributed turns"` | **0 hits** (3 before: 2 in `agents.tsx`, 1 in `agent-detail.tsx`) |
| 23 | `git grep -n "attributed"` (case-insensitive, `Frontend/`) | 0 hits |
| 24 | `git grep -n "Share of turns"` | 1 hit — deliberately unchanged |
| 25 | `/agents` renders | hero + column both read **Caller turns**; numbers identical to before |
| 26 | Open a persona modal | `Observed activity` reads **Caller turns** / Share of turns / Last seen |
| 27 | Identifiers unmoved | `git grep -n "turnShare\|total_turns\|mergeAgentRows"` — same count as before |

### 5.4 C-3 specific

| # | Check | Expected |
| --- | --- | --- |
| 28 | `deploy/README.md` exists, untracked | appears in `git status` |
| 29 | `git diff --stat -- infra/` | **empty** — the compose file is documented, not edited |
| 30 | Run the two `env \| grep '^POLICY_'` commands from the doc | identical output from both containers |

**Item 30 is a live check worth running now**, not just after a future deploy. It is the only way to confirm the invariant currently holds on your machine, and it costs two commands.

---

## §6. Ambiguities and confirmations needed

### §6-A — C-1: narrow the sum, or relabel only?

The recommended patch does **two** things: relabels, *and* stops summing `draft`/`void`. The second changes the displayed number.

| Option | Effect |
| --- | --- |
| **A1 — narrow the sum (recommended)** | `Unpaid total` excludes `draft`/`void`. The number becomes correct. Risk: the footer no longer equals the visible column sum when such rows exist — mitigated because those rows chip as `draft`/`archived`, which reads as "not money". |
| **A2 — relabel only** | Keep `invoices.reduce(...)` exactly as it is; change `outstandingTotal` → `unpaidTotal` and the label → `Unpaid total`, nothing else. Smaller diff, but `void` invoices still count as unpaid, which is not true. |

If you want **A2**, use this instead of the §4.1 block and change nothing else:

```ts
/**
 * Sum of every invoice `customer_360` returned, for the panel's summary line.
 *
 * That projection filters on `status != "paid"`, so this includes `draft` and `void`
 * rows, which nobody owes. Narrowing it is FEATURE_20 §6-A option A1.
 */
export function unpaidTotal(invoices: Array<{ amount: number }>): number {
  return invoices.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
}
```

(with A2, drop `status` from the §4.2 reasoning — the call site is unchanged either way.)

**My recommendation is A1.** A number labelled as money should not include cancelled invoices, and the whole point of this cookbook is that a label and its number have to agree.

### §6-B — expose `Invoice.outstanding_amount`? *(recommend: yes, as its own cookbook)*

Even after A1, the figure is **face value**. A `partial` invoice contributes its full `total_amount` although part of it has been paid. The correct number is persisted, one column away, and never leaves the server.

Fixing it is genuinely additive — one key in the `customer_360` projection:

```python
{"invoice": i.invoice_number, "amount": float(i.total_amount),
 "outstanding": float(i.outstanding_amount), "status": i.status}
```

That is the same shape of change as the approved C13 additive keys on `escalations()` (`created_at`, `customer_id`), which carry the in-code note *"Additive keys — consumed by the admin dashboard only; supervisor-dashboard ignores them."* So there is precedent, and it is JSON-additive and safe.

I have **not** built it here because it is not a labelling defect, it changes the endpoint payload, it needs a per-row UI decision (show both amounts? only when they differ?), and it requires a container rebuild — none of which belong in a corrections cookbook. **Say the word and it becomes FEATURE_21.** Given your live data has `partial` invoices, this is the highest-value item on the list.

### §6-C — `customer_360`'s `!= "paid"` filter *(flagged, not built)*

The root cause of C-1 is the filter itself. A whitelist would be correct:

```python
for i in invoices if i.status in ("issued", "partial", "overdue", "disputed")
```

I did **not** write this. It modifies existing backend behaviour for an existing consumer, which is constraint 2 (backend core logic is locked) — the same reasoning that parked FEATURE_19. C-1 achieves the correct *displayed* result from the frontend without touching it. If you want the server corrected instead, that is a one-line change and an explicit unlock from you.

### §6-D — C-2: verify the caller-turn claim before applying *(action required)*

**I could not verify this from the branch.** The C12 backlog records that the turn writer only ever emits `speaker="caller"`, and `agent_activity` has no `speaker` predicate — but I did not re-read the writer this session, and FEATURE_18 demonstrated that GitHub's code-search index silently returns zero hits for tokens that demonstrably exist in this repo. I am not asserting it.

**Run this first:**

```bash
git grep -n "speaker" -- packages/persistence apps/agent-worker | grep -v test
```

| Result | Apply |
| --- | --- |
| Every write site passes `speaker="caller"` (or equivalent) and nothing writes an agent speaker | **§4.4 + §4.5 as written** — `Caller turns` |
| Some site writes an agent/assistant speaker | **fallback below** — `Turns handled` |

**Fallback**, if the grep contradicts C12. Same five locations, different word — this is true regardless of what `speaker` contains, because the metric is `count(Turn.id)` grouped by `active_agent`:

| Location | Fallback text |
| --- | --- |
| `agents.tsx` HeroStat `label` | `Turns handled` |
| `agents.tsx` idle StatCard `context` | `No turns handled` |
| `agents.tsx` `<Th align="right">` | `Turns handled` |
| `agents.tsx` EmptyState `description` | `No turns were handled by a persona in this window.` |
| `agent-detail.tsx` caption | `Turns handled` |

Either way the current word `Attributed` goes: it is vague enough to be read as persona output, which the metric certainly is not.

### §6-E — the two unmirrored `POLICY_*` thresholds *(flagged, not built)*

`POLICY_TOPUP_DENOMINATIONS_TND` and `POLICY_PLAN_CODES` are enforced by `PolicyThresholds` and absent from `policy_view._DEFAULTS` / `GOVERNED_BY`. A supervisor on `/policies` cannot see them.

Mirroring them means adding entries to `_DEFAULTS`, `GOVERNED_BY` and `enforced_definitions()` — and, critically, **knowing which `reference.business_rules` rule ids they govern.** I do not know that from the branch; `GOVERNED_BY` currently maps only `RULE_BILLING_CAP` and `RULE_DEFERRAL_ELIGIBILITY`, and `business_rules` has 6 rows. It also touches `tests/test_policy_view.py`, which is the pin holding the enforcer and the registry together.

Documented in `deploy/README.md` as a known gap. If you want it closed, tell me which rule ids own those two thresholds and it becomes its own cookbook.

### §6-F — split this cookbook?

If you would rather have three separate documents (`FEATURE_20` / `21` / `22`), say so and I will split it. I bundled them on the `RUNBOOK_V2_CORRECTIONS.md` precedent and because each is under 15 lines; the three patches are already disjoint by file, so splitting costs nothing but numbering.

---

## §7. Summary of the working tree after this patch

**Modified (tracked):**
- `Frontend/admin_dashboard/src/lib/nexus/customer-view.ts` *(C-1)*
- `Frontend/admin_dashboard/src/components/nexus/customer-detail.tsx` *(C-1)*
- `Frontend/admin_dashboard/src/routes/agents.tsx` *(C-2)*
- `Frontend/admin_dashboard/src/components/nexus/agent-detail.tsx` *(C-2)*

**New (untracked):**
- `deploy/README.md` *(C-3)*

**Untouched, and verifiable as empty diffs:** all of `apps/`, `services/`, `packages/`, `infra/`; `src/lib/nexus/status.ts`; `src/routeTree.gen.ts`; `package.json`; every `*.server.ts`; every `query-keys.ts` namespace.

**No container rebuild. No migration. No new test. `pytest` stays at 28.**


On your §6-B resolution
You were right to grep and I was right not to assert. sip_transfer.py:87-88 calls notify_advisor with template="advisor_callback" — so those customer_id = NULL rows have a real, live producer, and "Unattributed" is describing traffic that actually flows. That's the second time in this series (formatInstant in F17, this in F18) that the difference between verified and assumed changed the outcome. I've carried the same discipline into §6-D below.
Your 48 | 48 | 3 corroboration is the D18.5 proof in one line: 48 rows, 48 sent_at values, 28 of them failed. A column labelled "Sent" would have been wrong on 58% of the table.
Why three items in one document
The standing rule is one feature per cookbook. These aren't features — they're the three corrections your §6-E left on the backlog, and each is under 15 lines. The tree already bundles corrections (RUNBOOK_V2_CORRECTIONS.md) while splitting features, so I followed that. §6-F offers the split if you'd rather. Numbering skips to 20 because §6-D reserved 19 for the parked failure-reason capture.
What the "Total invoiced" mislabel turned out to be
Three defects stacked, not one:
customer_360 builds open_invoices from if i.status != "paid" and projects float(i.total_amount). The frontend then sums that with a helper named outstandingTotal and labels the result "Total invoiced".
It isn't the total invoiced — paid invoices are filtered out upstream.
It isn't outstanding either — Invoice.outstanding_amount exists, is nullable=False, and is never projected. The sum is face value. Your live data has partial invoices, so this one is active today, not theoretical.
!= "paid" is a blacklist, not a whitelist. The CHECK constraint allows seven statuses, so draft (never issued) and void (cancelled) are both being added into a number rendered as money — inside a section whose empty caption reads "Nothing outstanding."
Defect 3 is the one that isn't a wording problem. The fix narrows the sum in the frontend and relabels to "Unpaid total"; the rows stay visible and chipped. Correcting the server filter would be cleaner but it modifies existing endpoint behaviour, so it's flagged in §6-C, not built — same reasoning that parked FEATURE_19.
Two things that are different from F16–F18
No container rebuild. No route, no repository method, no Python at all. pytest stays at 28 and routeTree.gen.ts must come back empty — if it moves, something else moved it.
§6-D needs one command before you apply C-2. I could not re-verify the "turns are caller-only" claim from the branch, and F18 proved the code index lies about this repo. Run git grep -n "speaker" -- packages/persistence apps/agent-worker | grep -v test and pick between two fully-written label sets — Caller turns if C12 holds, Turns handled if it doesn't. The second is true either way, since the metric is count(Turn.id) grouped by active_agent with no speaker predicate.
The D13 finding grew
Writing it up surfaced something the backlog note didn't have: policy_view._DEFAULTS mirrors four of the enforcer's six thresholds. POLICY_TOPUP_DENOMINATIONS_TND and POLICY_PLAN_CODES are enforced by PolicyThresholds and invisible on /policies. Closing that needs the rule-id mapping, which isn't in the branch — §6-E.
The doc lands at deploy/README.md, beside helm/ and secrets/, since docs/ holds only versions/ and deploy/ has no root file. It's outside the services/ infra/ packages/ diff gate, so your existing check stays clean.
Highest-value follow-up remains §6-B — projecting outstanding_amount additively, the same shape as the approved C13 keys on escalations(). Say the word and it becomes FEATURE_21.