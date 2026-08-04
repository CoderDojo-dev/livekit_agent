# Cookbook 8 — Decisions & Requested-Actions Ledger (Admin Dashboard)

> Branch target: local `version_80` (HEAD `eda5f58`)
> Scope: `Frontend/admin_dashboard/` + **2 additive backend lines** (Rule 3c)
> New route: `/decisions` · `/rules` still untouched
> Status: designed, not applied

---

## §0 — The finding that shapes the whole page

`packages/persistence/src/persistence/models/execution.py` (SHA `4ef95332…`), module docstring:

> "`idempotency_key` is UNIQUE — the contract that an action runs at most once across retries.
> **Every row references the `policy_verdict_id` that authorized it (no action without a
> verdict).**"

And the column is not nullable:

```python
policy_verdict_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("policy.policy_verdicts.id"), nullable=False
)
```

This answers the design question before I ask it. You listed *"Decisions and requested actions
logs"* as one feature, and the schema agrees: **every action is the child of exactly one verdict.**
They are not two tables that happen to sit near each other — they are a decision and its
consequence, joined by a mandatory foreign key.

So this ships as **one page with a parent/child shape**, not two tables:

> *The agent asked to do X → the policy engine returned AUTHORIZED/REFUSED/ESCALATE because of rule
> R → and here is what actually happened when we tried to execute it.*

That chain is the single most valuable thing in this backend for a supervisor, and it currently has
**no surface in the dashboard at all**. Building it as two disconnected tables would throw away the
foreign key that makes it meaningful.

---

## §1 — Where it lands, and why not `/rules` or `/conversations`

I recommended in Cookbook 7 §8.1 that `/rules` could host this data. **I am not doing that**, and
the reason matters: you have not answered §8.1, and hijacking a route whose fate is undecided would
quietly pre-empt your decision. If you later choose §8.1 option 1 (delete `/rules`), nothing here
needs to move.

I also read `conversations.tsx` (SHA `99ead9ea…`) — the last unread mock — specifically to rule it
in or out as the landing site. It is **out**, and it produced two separate flags of its own (§9).

**Decision: a new route `/decisions`.** Precedent is Feature 2, which added `/availability` and
shipped fine. `/rules` stays untouched at zero diff, still flagged.

---

## §2 — Backend reference

### 2.1 `PolicyVerdict` — `policy.py` (`030ff96f…`)

`policy.policy_verdicts`, **append-only** (docstring: *"every authorize/refuse/escalate decision,
append-only"*).

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID NOT NULL, indexed | cross-link to `/calls` |
| `customer_id` | UUID **nullable** | |
| `requested_action` | `String(80)` NOT NULL, indexed | what the agent asked to do |
| `direction` | `String(10)` NOT NULL default `'inbound'` | `inbound` \| `outbound` |
| `verdict` | `String(12)` NOT NULL | **`AUTHORIZED` \| `REFUSED` \| `ESCALATE`** |
| `rule_id` | `String(80)` NOT NULL | → joins Cookbook 7's registry |
| `justification` | `Text` **NOT NULL** | the human-readable reason |
| `inputs_snapshot` | `JSONB` NOT NULL | the evidence the decision was made on |
| `created_at` | tz-aware, `now()` | **a real timestamp** |

Note `rule_id` is the same vocabulary as `reference.business_rules.rule_id` from Cookbook 7 — but
there is **no foreign key** between them, so a verdict may cite a rule id absent from the registry.
Handled in G6.

### 2.2 `ActionLedger` — `execution.py` (`4ef95332…`)

`execution.action_ledger`, `UUIDPrimaryKey, Timestamps, Base`.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID NOT NULL, indexed | |
| `customer_id` / `subscription_id` | UUID nullable | |
| `action_type` | `String(80)` NOT NULL | |
| `target_domain` | `String(20)` NOT NULL | |
| `idempotency_key` | `String(80)` NOT NULL **unique** | the at-most-once contract |
| `policy_verdict_id` | UUID NOT NULL **FK** | §0 |
| `parameters` | `JSONB` NOT NULL | |
| `status` | `String(20)` default `'pending'` | **`pending`\|`succeeded`\|`failed`\|`retrying`** |
| `attempt_count` | `Integer` default `0` | |
| `adapter_reference` | `String(120)` nullable | |
| `error_message` | `Text` nullable | **why it failed** |

`Timestamps` → `created_at`, `updated_at` both exist.

### 2.3 What the existing endpoints actually project

```python
def verdicts(self, session_id: str) -> list[dict]:
    ...
    return [{"id": ..., "action": v.requested_action, "verdict": v.verdict,
             "rule_id": v.rule_id, "justification": v.justification} for v in rows]

def actions(self, status: str = "failed") -> list[dict]:
    ...
    return [{"id": ..., "action_type": a.action_type, "status": a.status,
             "idempotency_key": a.idempotency_key, "reference": a.adapter_reference} for a in rows]
```

**Both projections drop most of the value.**

`verdicts()` omits `direction`, `customer_id`, `inputs_snapshot`, `created_at`.
`actions()` omits `error_message`, `attempt_count`, `created_at`, `session_id`, `target_domain`,
`parameters`, and — critically — `policy_verdict_id`, the key that links the two.

A failed-actions table without `error_message` or `attempt_count` cannot answer "why did it fail
and how many times did we try". It is a list of names.

### 2.4 The two structural walls

**Wall 1 — `session_id` is a required query parameter.**

```python
@app.get("/api/v1/policy/verdicts")
def verdicts(session_id: str, session: DbSession, role: SuperviseurRole) -> dict:
```

No default → FastAPI makes it **mandatory**; omitting it is a 422. There is no estate-wide verdict
list. Structurally identical to Feature 5's `lookup_tickets` (per-customer only) and Feature 4's
missing session index — **third occurrence of this pattern**: the read API was built for the agent
asking about one entity, not for a supervisor surveying the estate.

**Wall 2 — no join surface.** Nothing exposes the verdict→actions relationship, even though the FK
is mandatory.

---

## §3 — Endpoints

### 3.1 New backend surface (Rule 3c)

Rule 3(c) permits *"missing endpoints that expose existing backend functionality/data"* — creating
access, not features. Both walls are access problems: the data exists, is already persisted, and is
already read by this exact repository class. No business logic is added.

Following the Feature 4 precedent exactly (**+1 repository method, +1 route**):

#### `SupervisionRepository.decision_ledger(...)` — `repositories.py`

```python
def decision_ledger(self, verdict: str | None = None, session_id: str | None = None,
                    limit: int = 100) -> list[dict]:
    """Verdicts newest-first, each with the actions it authorized. Read-only."""
```

- `select(PolicyVerdict).order_by(PolicyVerdict.created_at.desc()).limit(limit)`
- optional `.where(PolicyVerdict.verdict == verdict)` and `.where(PolicyVerdict.session_id == sid)`
- `session_id` parsed with the existing `to_uuid`; invalid → `[]` (mirrors `verdicts()`)
- one follow-up `select(ActionLedger).where(ActionLedger.policy_verdict_id.in_(ids))` grouped in
  Python — **avoids N+1**, and mirrors the batching style already used in `system_overview`

Projection — every field the UI needs, nothing invented:

```jsonc
{
  "id": "…", "session_id": "…", "customer_id": "…|null",
  "action": "…",            // requested_action, same key name as verdicts() for consistency
  "direction": "inbound",
  "verdict": "AUTHORIZED",
  "rule_id": "RULE_BILLING_CAP",
  "justification": "…",
  "inputs_snapshot": { },
  "created_at": "2026-08-03T10:12:44+00:00",
  "actions": [
    { "id": "…", "action_type": "…", "target_domain": "…", "status": "failed",
      "attempt_count": 3, "idempotency_key": "…", "reference": "…|null",
      "error_message": "…|null", "parameters": { },
      "created_at": "…", "updated_at": "…" }
  ]
}
```

**`created_at` must be serialised as an ISO-8601 string**, not handed to FastAPI as a raw
`datetime`, so the wire shape matches every other endpoint in this API (`availability` already does
this). Use `.isoformat()`.

#### `GET /api/v1/decisions` — `main.py`, role `superviseur`

```python
@app.get("/api/v1/decisions")
def decisions(session: DbSession, role: SuperviseurRole, verdict: str | None = None,
              session_id: str | None = None, limit: int = 100) -> dict:
    """Policy decisions newest-first with the actions they authorized (supervision review)."""
    return {"decisions": SupervisionRepository(session).decision_ledger(verdict, session_id, limit)}
```

**Placement:** immediately after the existing `/api/v1/policy/verdicts` route and before
`/api/v1/actions`, keeping the supervision block contiguous. No path-collision risk with the
`{advisor_id}`-style ordering hazard called out in `main.py`, since `/api/v1/decisions` is a
static segment in a namespace with no sibling path parameter.

**Nothing existing is modified.** `verdicts()`, `actions()`, `/policy/verdicts` and `/actions` keep
their exact current signatures and response shapes — I am not widening `actions()`'s projection,
because the agent-worker and any other consumer depend on it. Additive only.

### 3.2 Empty-filter convention — declared explicitly

Cookbook 3 used `status=""` to mean "all"; Cookbook 5 omitted the parameter entirely. I flagged
that the conflict must be resolved per cookbook.

**Cookbook 8 omits empty parameters entirely** (the Cookbook 5 convention), and the new endpoint is
designed to make that the *only* correct reading: `verdict` defaults to `None`, not `""`. An empty
string would fail the `verdict == ""` comparison and return zero rows — so the server function must
never send a blank `verdict`. This is enforced in the query-builder, not left to a call site.

### 3.3 CORS / middleware

No change — the Feature 0 proxy covers it.

---

## §4 — Findings

### G1 — Chip trap, sixth recurrence: **two of four action statuses are missing**

`ActionLedger.status IN ('pending','succeeded','failed','retrying')`.

Against `status.ts`: `pending` ✅ · `failed` ✅ · **`succeeded` ❌** · **`retrying` ❌**

Unmapped values make `StatusChip` return `null`, so **the success case — the majority of rows —
would render a blank cell.** Exactly the Feature 6 `ready` situation: the trap lands on the healthy
majority, which is where it is least likely to be noticed in a sparse test dataset and most
damaging in production.

Total mapping, reusing existing keys only:

| Backend | `status.ts` key | Why |
|---|---|---|
| `pending` | `pending` | exact |
| `succeeded` | `resolved` | `disc / low / soft` — the table's terminal-success tone |
| `failed` | `failed` | exact |
| `retrying` | `processing` | `half / medium / soft` — in-flight, not yet terminal |

`queued` was considered for `retrying` and rejected: queued implies not-yet-attempted, but
`retrying` always means `attempt_count >= 1`. `processing` carries the in-flight meaning correctly.

**Zero `status.ts` changes** — eighth consecutive cookbook.

### G2 — Verdicts are not statuses, and must not be forced into `status.ts`

`AUTHORIZED` / `REFUSED` / `ESCALATE` are uppercase and none exist in `status.ts`. The tempting move
is to map them to chips. I am not doing that, for a reason rooted in the file's own header:

> *"Chapter 1.7 — the canonical status truth table. **No status exists outside it.**"*

A verdict is a decision outcome, not a lifecycle status. `escalated` *does* exist and would map
perfectly for `ESCALATE` — but `AUTHORIZED` and `REFUSED` have no honest counterpart, and mapping
one of three to a chip while rendering the other two differently produces an incoherent column.

**Decision:** the Verdict column renders as `Token`, with `strong` for `ESCALATE`. Uniform, no
invented keys, no design-system extension. Raised as §8.1 in case you would rather add three chip
definitions — that is a `status.ts` change and therefore yours to approve, not mine to take.

Values are stored uppercase (enforced by `CheckConstraint`), and `telemetry_timeline` already
compares with `.upper()`. Compare against exact uppercase literals; do not lowercase for display
logic, only for presentation.

### G3 — Real timestamps at last, and the timezone rule still applies

Unlike Cookbooks 6 and 7, both tables carry genuine timestamps, so no substitute column is needed.

But Cookbook 2's inverted-timezone rule stands: `created_at` is **tz-aware UTC**, and the business
timezone is `Africa/Tunis` (`CALLBACK_TIMEZONE`). Rendering raw UTC would misreport every row by an
hour.

`format.ts` has no datetime formatter, and `formatBusinessTime` lives in Cookbook 3's
`callback-view.ts` — **which is not applied yet**. Cookbook 8 must not depend on unapplied work, so
it defines its own `formatInstant` in `decision-view.ts` using `Intl.DateTimeFormat` with an
explicit `timeZone`.

**Bans still enforced:** no `getDay(`, no `getHours(`, no `toLocaleString(`. If Cookbook 3 is
applied first, de-duplicate then — noted in §8.4 rather than creating a dependency now.

### G4 — `error_message` and `attempt_count` are the reason to build this page

The existing `/actions?status=failed` returns a name and an idempotency key. With the new
projection, a failed action shows **what broke and how many times it was retried**. That is the
difference between a log and a diagnostic tool, and it costs nothing — the columns are already
persisted and already loaded by the query.

`error_message` is `Text` and nullable: render only when present (the conditional-second-line rule
from Features 6 and 7), and truncate in the table with the full text in the detail modal.

### G5 — `inputs_snapshot` is the audit evidence; it belongs in a modal, not a cell

`JSONB`, NOT NULL, arbitrary shape — the snapshot of what the engine decided on. Same class of
problem as Cookbook 7's `definition`, but larger and genuinely unbounded, so the Cookbook 7
solution (inline key/value pairs) does not transfer.

It goes in a **detail modal**, together with `parameters`, the full `justification`, the full
`error_message`, and `idempotency_key`.

**The modal must `createPortal` to `document.body`.** This is the Feature 1 defect: `PageSection`
carries `.rise`, whose `transform` creates a containing block that clips `position: fixed`.
Cookbook 7 had no overlay so the hazard did not apply; here it does. Reuse the existing
`modal.tsx` from Feature 1 unchanged — it already portals correctly.

JSON is rendered with `JSON.stringify(value, null, 2)` inside the existing mono type token. **No
new syntax-highlighting dependency** — zero new npm packages holds.

### G6 — `rule_id` has no foreign key to the registry

`PolicyVerdict.rule_id` is a bare `String(80)`. `reference.business_rules.rule_id` is unique but
**not referenced**. So a verdict can cite a rule id that does not exist in Cookbook 7's registry —
legitimately, since the engine executes in code and the registry is a published catalog that can
lag.

So: render `rule_id` as a `Token`, and **do not** build a link or lookup into the registry that
would 404 or render blank for un-catalogued rules. Cross-linking the two is §8.3.

This is a genuine integrity gap worth naming: the registry a supervisor reviews and the rule ids
the engine emits are not constrained to agree. It is the same drift family that `policy_view.py`
was written to close for *thresholds*, left open for *rule identity*.

### G7 — Cross-link to the call, conditional on Feature 4

Every verdict has `session_id`. Feature 4's rewritten `calls.tsx` adds
`validateSearch: z.object({ session: z.string().uuid().optional() })`, so the natural affordance is
a link to `/calls?session=<id>`.

**Feature 4 is written but not applied.** So the link is specified as *conditional*: include it only
once Feature 4 is applied; until then render `session_id` as a plain `Token`. Stated in the
checklist so it cannot ship as a dead link.

Also note Feature 4's unfixed live bug (§8.7 there): `session_detail` calls
`float(call.max_frustration_score)` on a nullable column → unhandled 500. Following this link to a
session with a null frustration score will 500. **Not fixed here** — different feature, still
awaiting your approval — but the link makes it reachable from a second page, which slightly raises
its priority.

### G8 — `limit` is unbounded input

`list_callbacks` precedent uses `limit: int = 100`. Match it. The server function must not forward a
user-controlled `limit`; it is fixed at the call site. No pagination is designed (consistent with
every other list in this API), and the footer states the ceiling honestly: *showing the most recent
N decisions* — never a fabricated total, which would be the Feature 6 F12 mistake.

### G9 — `customer_id` is nullable on both tables

Nullable on `PolicyVerdict` and `ActionLedger` — the agent can be refused before identification.
Render `—`, never `null` or an empty `Avatar`. No customer-name lookup: that needs the
customer-search endpoint still missing since Cookbook 3.

### G10 — Verdict distribution already exists, for free

`telemetry_timeline()` already returns:

```python
"verdict_distribution": {"authorized": n, "refused": n, "escalated": n}
```

— over the **last 100 verdicts**, via the existing `GET /api/v1/telemetry/timeline` (`superviseur`).

That is a legitimate, already-exposed summary and I use it for the header stats. But two constraints:

1. It is capped at 100 and is **not** filtered by the page's filters — so it must be labelled
   *last 100 decisions*, not presented as an all-time total.
2. It must render via `Card`, **not `StatCard`** — `StatCard.delta` is non-optional and there is no
   delta in this data. Fabricating one is the standing prohibition from Feature 1. `Card` +
   `CardHeader` + `Token` carries it without inventing a trend.

### G11 — `direction` is a real dimension nobody surfaces

`inbound` | `outbound`, NOT NULL, currently projected by nothing. Rendered as a `Token` beside the
requested action. Not made a filter — no evidence yet that supervisors need to slice by it, and
adding an unused control is invention.

### G12 — React keys are safe on both levels

Verdict rows key on `id` (UUID PK). Nested actions key on `id` (UUID PK). `idempotency_key` is also
unique but is a business key — prefer the PK. No duplicate-key hazard, unlike Features 4–6.

---

## §5 — Frontend implementation plan

### 5.1 Files

| Action | Path |
|---|---|
| **new** | `src/lib/api/decisions.server.ts` |
| **new** | `src/lib/nexus/decision-view.ts` |
| **new** | `src/components/nexus/decision-detail.tsx` (modal, portals — G5) |
| **new** | `src/routes/decisions.tsx` |
| **modified** | `src/lib/nexus/query-keys.ts` — append `decisionKeys` |
| **modified** | `src/lib/nexus/nav.ts` — one entry + `PAGE_META` |
| **regenerated** | `routeTree.gen.ts` — by the router, not by hand |
| **backend** | `repositories.py` (+1 method), `main.py` (+1 route) |

Zero-diff: `status.ts`, `primitives.tsx`, `blocks.tsx`, `modal.tsx`, `format.ts`, `styles.css`,
`data.ts`, `rules.tsx`, `policies.tsx`, `conversations.tsx`.

**`data.ts` is untouched** — `/decisions` is a new route with no mock predecessor, so there is no
mock array to remove and no grep-guard needed. First cookbook in the series with no `data.ts` diff.

### 5.2 `decisions.server.ts`

```ts
export type DecisionAction = {
  id: string; action_type: string; target_domain: string;
  status: "pending" | "succeeded" | "failed" | "retrying";
  attempt_count: number; idempotency_key: string;
  reference: string | null; error_message: string | null;
  parameters: Record<string, unknown>;
  created_at: string; updated_at: string;
};

export type Decision = {
  id: string; session_id: string; customer_id: string | null;
  action: string; direction: "inbound" | "outbound";
  verdict: "AUTHORIZED" | "REFUSED" | "ESCALATE";
  rule_id: string; justification: string;
  inputs_snapshot: Record<string, unknown>;
  created_at: string;
  actions: DecisionAction[];
};
```

- `listDecisions` — `createServerFn({ method: "GET" })`, `requireRole("superviseur")` (**factory
  form**, per the Feature 2 correction; copy the composition from `availability.server.ts`).
  Builds `query` by **omitting** any empty value (§3.2), forwards a fixed `limit: 100`.
- `getVerdictDistribution` — reuses `GET /api/v1/telemetry/timeline`, returning only
  `verdict_distribution` (G10).

Both are reads — **no `POST` server functions**, so the React Start CSRF constraint from the
Feature 2 correction does not arise here.

### 5.3 `decision-view.ts` (pure, no JSX, no network)

- `actionStatusKey(status): StatusKey` — the four-way total mapping (G1).
- `verdictLabel(v)` / `isEscalate(v)` — G2.
- `formatInstant(iso: string): string` — `Intl.DateTimeFormat` with `timeZone`; no banned calls (G3).
- `actionRollup(d: Decision)` — `"3 actions · 1 failed"`, or `"No actions"` when the array is empty.
- `hasFailure(d)` — any child `failed`; drives the row emphasis.
- `decisionMatches(d, q)` — client-side over `action`, `rule_id`, `justification`, `session_id`.
- `truncate(text, n)` — for `justification` / `error_message` in cells.

### 5.4 `decisions.tsx`

One `PageSection` → a `Card` stat strip (G10) → a `TableShell`.

**Toolbar:** `SearchInput placeholder="Search decisions"` (client-side) + `Segmented` for verdict
scope: `All | Authorized | Refused | Escalate`.

> `Segmented` must emit `type="button"` — fixed during Feature 1 after it silently submitted a
> parent form. Verify the fix is present before reuse.

`All` sends **no** `verdict` parameter (§3.2).

**Columns:**

| Column | Align | Source |
|---|---|---|
| Decision | left | `action` in `t-ui text-ink-1`; `direction` `Token` beside it (G11) |
| Verdict | left | `Token`, `strong` when `ESCALATE` (G2) |
| Rule | left | `rule_id` `Token`, no registry link (G6) |
| Justification | left | truncated `t-caption text-ink-3` |
| Actions | left | `actionRollup` (G/5.3) |
| When | right | `formatInstant(created_at)`, `t-mono text-ink-3` (G3) |

Row `key={d.id}`, click opens the detail modal, preserving
`className="transition-colors duration-[120ms] hover:bg-surface-3"`.

The row is clickable, so it needs `role="button"`, `tabIndex={0}` and keyboard activation — the
global `:focus-visible` outline in `styles.css` already covers the focus ring; no new focus styling.

**Detail modal** (`decision-detail.tsx`): full `justification`, `inputs_snapshot`, `session_id`
(+ conditional `/calls` link, G7), `customer_id` or `—` (G9), then one block per action with
`action_type`, `target_domain`, `StatusChip`, `attempt_count`, `idempotency_key`, `reference`,
`error_message`, `parameters`, timestamps.

**States:** `TableSkeleton rows={8} cols={6}` · `TableErrorRow` with a specific 403 message ·
`EmptyState` distinct from error (Feature 6 F10) · a filtered-empty message distinct from a
truly-empty ledger.

**Footer:** `Showing the most recent {n} decisions` (G8).

### 5.5 `nav.ts`

One entry, `INSIGHTS` section, label **Decisions**.

**Shortcut:** `G A` is Advisors and `G D` is Availability — both already taken, and Feature 2 shipped
`G D` only after `G A` collided. **Verify the full shortcut list in `nav.ts` before assigning.**
Proposed: **`G K`**. If taken, fall back to `G J`. Do not ship a duplicate.

---

## §6 — Design-system compliance

| Constraint | Status |
|---|---|
| New colours / spacing / radius / type tokens | none |
| New component shapes | none — existing primitives + Feature 1 `Modal` |
| New npm dependencies | **zero** (JSON via `JSON.stringify`) |
| New `status.ts` keys | **zero** (8th consecutive) |
| `StatCard` with fabricated delta | none — `Card` used instead (G10) |
| Overlay portals to `document.body` | **required** (G5) |
| Backend | +1 method, +1 route, **0 modifications** |
| Lint baseline | must return to exactly **36 problems** |

---

## §7 — Validation checklist

**Static**

- [ ] `tsc --noEmit` clean · `eslint` at the exact 36-problem baseline · `build` exit 0.
- [ ] `git diff` on backend touches **only** `repositories.py` (+1 method) and `main.py` (+1 route).
- [ ] `verdicts()`, `actions()`, `/policy/verdicts`, `/actions` — **byte-identical**.
- [ ] `routeTree.gen.ts` regenerated by the router, containing exactly one `/decisions` line.
- [ ] `data.ts`, `status.ts`, `rules.tsx`, `policies.tsx`, `conversations.tsx` — zero diff.
- [ ] `grep -n "getDay(\|getHours(\|toLocaleString(" src/` → no new hits (G3).
- [ ] No raw hex or `rgb(` introduced.

**Backend**

- [ ] `GET /api/v1/decisions` → 200, newest-first.
- [ ] `?verdict=REFUSED` filters; `?verdict=` (blank) is **never sent** by the client (§3.2).
- [ ] `?session_id=<invalid-uuid>` → `[]`, not a 500.
- [ ] `created_at` is an ISO **string** on the wire, not a serialised datetime object.
- [ ] A verdict with zero actions returns `"actions": []`, not `null`.
- [ ] N+1 check: one verdict query + one action query, regardless of row count.

**Behavioural — the specific regressions to hunt**

- [ ] **A `succeeded` action renders a visible chip, not a blank cell** (G1). This is the single
      highest-risk defect in the cookbook — it hits the majority row.
- [ ] A `retrying` action renders `processing`, not blank.
- [ ] All three verdicts render; `ESCALATE` is visually distinct (G2).
- [ ] Timestamps display in `Africa/Tunis`, one hour ahead of the stored UTC value (G3).
- [ ] A failed action shows `error_message` and `attempt_count` in the modal (G4).
- [ ] **The modal is not clipped** — the scrim covers the full viewport, confirming it portals to
      `document.body` and is not trapped by `.rise` (G5). Verify by measuring the scrim rect, the
      way the Feature 1 defect was caught.
- [ ] A verdict citing an un-catalogued `rule_id` renders a plain `Token` with no dead link (G6).
- [ ] `customer_id: null` renders `—` (G9).
- [ ] Verdict distribution is labelled *last 100*, never as an all-time total (G10).
- [ ] Filtered-empty and truly-empty produce different messages.
- [ ] Row is keyboard-activatable and shows the standard focus ring.

**Conditional on Feature 4**

- [ ] If Feature 4 is applied → the `/calls?session=` link resolves. If not → **no link is
      rendered** (G7).

**Roles**

- [ ] `superviseur` and `administrateur`: page loads. `conseiller`: nav hidden, direct navigation
      yields the specific 403 message.

**Network**

- [ ] Zero direct browser requests to `:8108`.

---

## §8 — Open questions

**§8.1 — Add `authorized` / `refused` chip definitions to `status.ts`?** (G2)
I rendered verdicts as `Token` to avoid inventing keys in a file that declares no status may exist
outside it. Three new definitions would give a stronger column. `status.ts` is design-system
territory — your call, not mine.

**§8.2 — Should `/actions?status=failed` keep its own page?**
The new ledger subsumes it with more context. I left the endpoint untouched and built no separate
actions page. If you want a dedicated failed-actions queue, say so — it is a filtered view of the
same endpoint, roughly 40 lines.

**§8.3 — Cross-link `rule_id` to the Cookbook 7 registry?** (G6)
Blocked by the missing FK: some rule ids will not resolve. Doable with a graceful "not in registry"
state, but that is a real integrity gap worth deciding deliberately rather than papering over.

**§8.4 — De-duplicate `formatInstant` and `formatBusinessTime`.** (G3)
Cookbook 3 defines a business-time formatter that is not applied yet. Whichever lands second should
merge into a shared helper in `format.ts` — which would also give the series a single place where
the timezone rule is enforced.

**§8.5 — Pagination.**
Capped at 100, newest-first, no pagination — consistent with every other list here. `policy_verdicts`
is append-only and will grow without bound, so this is the list most likely to need paging first.

**§8.6 — The Feature 4 `max_frustration` 500 is now reachable from two pages.** (G7)
Still unapproved, still one null-guard. This cookbook adds a second route to it.

---

## §9 — Two separate flags from `conversations.tsx`

Read to evaluate it as a landing site (§1); rejected, but it surfaced two issues that belong on the
record rather than in this feature.

**§9.1 — The reply composer has no backend.** The page renders "Attach", a text input, and "Send".
Nothing in the backend accepts an outbound message into a session. `conversation.turns` is
**append-only, written by the agent-worker through a non-blocking async writer, never on the voice
path** — a dashboard write into that table would corrupt the conversation record. Same class as
Cookbook 7's `/rules`: **the feature does not exist**, so under Rule 3 it must be flagged, not built.

**§9.2 — It contains a second, competing ingestion UI.** The right-hand panel renders
`INGESTED_FILES` with a drop zone and "Browse files" — duplicating what Cookbook 6 wired properly at
`/knowledge` against `knowledge-service:8102`. Two upload surfaces with one real backend will
diverge. Recommendation: remove that panel when `/conversations` is addressed, leaving `/knowledge`
as the single ingestion surface. Not done here — out of scope, zero diff.

Both make `/conversations` a poor candidate for real wiring until you decide what it should be. It
is now the **third** template page with no backing feature (`/rules`, `/settings`, `/conversations`).

---

## §10 — Diff summary

```
 Frontend/admin_dashboard/
   src/lib/api/decisions.server.ts        | new
   src/lib/nexus/decision-view.ts         | new
   src/components/nexus/decision-detail.tsx | new
   src/routes/decisions.tsx               | new
   src/lib/nexus/query-keys.ts            | +decisionKeys
   src/lib/nexus/nav.ts                   | +1 entry, +PAGE_META
   routeTree.gen.ts                       | regenerated (+1 line)

 apps/business-api/src/business_api/
   repositories.py                        | +1 method  (decision_ledger)
   main.py                                | +1 route   (GET /api/v1/decisions)
```

Zero new dependencies · zero new tokens · zero new status keys · zero `data.ts` changes ·
zero CORS changes · zero backend modifications (additive only) · zero mutations.

---

## §11 — Next feature

**KPIs / Analytics** — `/analytics` and `/overview`, the last two admin pages with real backing.

Three endpoints already exist, all `superviseur`:

- `GET /api/v1/kpis` → `compute_kpis(...)` returned as `Kpis.__dict__`
- `GET /api/v1/system/overview` → `{metrics{7 counts}, services[11]}`
- `GET /api/v1/telemetry/timeline` → `{timeline[≤50], verdict_distribution}`

Four issues are already visible from what I have read:

1. **`system_overview`'s service list is hardcoded** — all eleven entries are literal
   `"status": "online"` strings. Nothing probes anything. Rendering that as a health matrix would
   be a dashboard that reports "all systems online" during a total outage. This will be the
   headline finding, and it is the most dangerous thing found in the series so far.
2. **`telemetry_timeline` timestamps are pre-formatted `"%H:%M:%S"` strings** with no date and no
   timezone — unusable for a real time axis, and they silently wrap at midnight.
3. `kpis.py` (`fb5afcd8`) is still unread — `Kpis` and `compute_kpis` shapes unknown.
4. `StatCard.delta` is non-optional, and **none** of these endpoints returns a period comparison.
   The overview mock is built entirely from deltas. That collision has to be resolved honestly
   rather than by fabricating trends.

Reads required: `kpis.py`, `overview.tsx` (`96a3f25d`), `analytics.tsx` (`a3cae255`).
