# Cookbook 7 — Guardrails & Policies (Admin Dashboard)

> Branch target: local `version_80` (HEAD `eda5f58`)
> Scope: `Frontend/admin_dashboard/` only
> Backend files modified: **ZERO** · created: **ZERO**
> Status: designed, not applied

---

## §0 — The request, and the answer the source gives

You asked for **"Guardrails (viewing + possibility of modification)"**.

Viewing: fully supported, and richer than the mock imagines.

Modification: **structurally impossible by deliberate design.** Not an oversight, not a missing
endpoint — the backend contains a module whose entire purpose is to prevent the thing the mock's
"New policy" button implies. This is the central finding of the cookbook, so I want to show the
evidence before designing anything.

`apps/business-api/src/business_api/policy_view.py` (SHA `5f725f46…`), module docstring:

> "The deterministic policy engine (policy-service) is twelve-factor: it reads its numeric
> thresholds from `POLICY_*` environment variables, **never from a table**. The
> `reference.business_rules` table is the governance record (rule id, domain, description,
> version, active) — it **must NOT carry its own copy of those numbers**, or the registry a
> supervisor reviews can silently drift from what is actually enforced (e.g. the table says cap
> 200 while `POLICY_PAYMENT_CAP_TND=500` is enforced)."

And `packages/persistence/src/persistence/models/reference.py` (SHA `01b2a098…`):

> "`business_rules` is the versioned, governable registry of the Policy rules … **the
> deterministic engine still executes in code**, while this table is the published, audited
> catalog that the business-api exposes for review/versioning."

So an "edit threshold" control would be a lie, and it would be a lie in **two different ways**
depending on which rule you edited:

1. **Governed rules** (`RULE_BILLING_CAP`, `RULE_DEFERRAL_ELIGIBILITY`). `overlay()` *replaces*
   `definition` with the live env values at read time. A write to `definition_json` would appear
   to succeed, then **vanish on the very next page load** — overwritten by the overlay.
2. **Non-governed rules.** A write would persist and display… and change nothing whatsoever,
   because the engine executes in code. You would end up with a dashboard confidently showing a
   cap of 500 while the agent enforces 200.

The second is worse than the first, because it never corrects itself.

**This is the second occurrence of a hazard class this series has already met.** Feature 5, F3:
writing `ticketing.tickets` from the dashboard would be silently reverted by `upsert_from_glpi()`.
Same shape — a table that *looks* writable but has an authoritative upstream that overwrites it.
The rule I proposed there generalises cleanly and I am now treating it as binding for the rest of
the series:

> **Never expose a write to a projection whose values are overwritten from an upstream source of
> truth. Find the upstream, or make the surface read-only and say why.**

Here the upstream is the environment, and the environment is changed by deployment, not by a
dashboard.

### Decision

**`/policies` ships read-only, with the enforcement provenance made visible.** The "New policy"
button is **removed, not disabled** — exactly as Feature 5 removed "New ticket". A disabled button
is a promise that the capability is coming; removal plus an explanatory caption is honest.

And the page gains something the mock never had: a visible statement of **where each number
actually comes from**. That is the genuinely useful answer to "can I see the guardrails" — more
useful than an edit box that would have lied.

---

## §1 — ⚠️ `/rules` has no backend at all

The mock `/rules` page (SHA `44a50614…`) renders `RULES` with columns **Rule · Trigger · Action ·
Runs · Status** and a "New rule" button. That describes a **trigger→action automation engine**.

There is no such engine anywhere in this backend.

`reference.business_rules` is not it. That table is `rule_id, domain, description,
definition_json, version, active` — policy governance metadata. It has no trigger, no action, and
no run counter. Nothing in the repository counts rule executions. I checked the full route table in
`main.py` (all 34 routes, SHA `ff52daff…`): there is no automation surface.

Your Rule 3 is explicit about this case:

> "If a feature seems to not exist in the backend at all… flag it — do not build the missing
> business logic yourself."

**So I am flagging it and building nothing.** This is the first genuine "the feature does not
exist" flag in the series. Building it would mean inventing an automation engine, a persistence
schema, an execution loop and a run counter — that is a backend feature, not frontend wiring.

`/rules` is therefore **out of scope for this cookbook and left untouched** — still on mock data,
zero diff. Three honest options in §8.1.

My recommendation is there too: the strongest candidate for that route is the **policy verdict
ledger**, which is real, substantial, and currently has no home in the dashboard. But that data is
exactly what you listed as *"Decisions and requested actions logs"* — the next feature — so it
belongs in Cookbook 8, not smuggled in here under a name that does not match it.

---

## §2 — Backend reference

### 2.1 `reference.BusinessRule` — `reference.py` (`01b2a098…`)

`UUIDPrimaryKey, Timestamps, Base` → `reference.business_rules`.

| Column | Type | Notes |
|---|---|---|
| `rule_id` | `String(80)` NOT NULL **unique** | e.g. `RULE_BILLING_CAP` — safe React key |
| `domain` | `String(40)` NOT NULL | grouping dimension |
| `description` | `Text` **nullable** | |
| `definition_json` | `JSONB` NOT NULL default `{}` | **variable shape**, see G4 |
| `version` | `Integer` NOT NULL default `1` | |
| `active` | `Boolean` NOT NULL default `true` | **boolean, not a status string** — G3 |

`Timestamps` supplies `created_at`/`updated_at` — but neither is projected into the API response.

### 2.2 `SupervisionRepository.business_rules()` — `repositories.py` (`0f9acd1f…`)

```python
rows = self._s.scalars(select(BusinessRule).order_by(BusinessRule.domain, BusinessRule.rule_id)).all()
return [
    {"rule_id": r.rule_id, "domain": r.domain, "version": r.version, "active": r.active,
     "description": r.description, "definition": r.definition_json}
    for r in rows
]
```

Note `definition_json` is renamed to **`definition`** on the wire. Ordered by `domain`, then
`rule_id`. No timestamps. No pagination.

### 2.3 `policy_view.overlay()` — `policy_view.py` (`5f725f46…`)

```python
GOVERNED_BY: dict[str, list[str]] = {
    "RULE_BILLING_CAP": ["POLICY_PAYMENT_CAP_TND"],
    "RULE_DEFERRAL_ELIGIBILITY": [
        "POLICY_DEFERRAL_MIN_AGE_DAYS",
        "POLICY_DEFERRAL_MAX_PER_YEAR",
        "POLICY_DEFERRAL_UNPAID_THRESHOLD_TND",
    ],
}
_SOURCE = "policy-engine (POLICY_* env)"
```

Defaults, which **must** match `policy_service.config.PolicyThresholds` and are pinned by
`tests/test_policy_view.py`:

| Env var | Default |
|---|---|
| `POLICY_PAYMENT_CAP_TND` | `200.0` |
| `POLICY_DEFERRAL_MIN_AGE_DAYS` | `180` |
| `POLICY_DEFERRAL_MAX_PER_YEAR` | `2` |
| `POLICY_DEFERRAL_UNPAID_THRESHOLD_TND` | `150.0` |

For a governed rule, `overlay()` sets `definition` to the enforced numbers and adds
`enforced: True`, `governed_by: [...]`, `source: "policy-engine (POLICY_* env)"`.
For every other rule it adds **`enforced: False`** and passes the row through unchanged.

Enforced definition keys, verbatim:

- `RULE_BILLING_CAP` → `{ "max_payment_tnd": <num> }`
- `RULE_DEFERRAL_ELIGIBILITY` → `{ "min_account_age_days": <num>, "max_deferrals_per_year": <num>, "unpaid_review_threshold_tnd": <num> }`

### 2.4 The route — `main.py` (`ff52daff…`), verified verbatim

```python
@app.get("/api/v1/reference/business-rules")
def business_rules(session: DbSession, role: AdministrateurRole) -> dict:
    rows = SupervisionRepository(session).business_rules()
    return {"rules": policy_view.overlay(rows)}
```

I read this specifically rather than inferring it. The existence of `overlay()` made it *likely*
that the route applied it, but "likely" is not a contract — and whether `enforced` / `governed_by`
/ `source` appear in the response determines roughly half of this page's design. It does apply.

---

## §3 — Endpoints

### 3.1 Existing, to reuse

#### `GET /api/v1/reference/business-rules` — role **`administrateur`**

No parameters. Returns:

```jsonc
{
  "rules": [
    {
      "rule_id": "RULE_BILLING_CAP",
      "domain": "billing",
      "version": 1,
      "active": true,
      "description": "...",          // string | null
      "definition": { "max_payment_tnd": 200.0 },
      "enforced": true,               // added by overlay()
      "governed_by": ["POLICY_PAYMENT_CAP_TND"],
      "source": "policy-engine (POLICY_* env)"
    },
    {
      "rule_id": "RULE_SOMETHING_ELSE",
      "domain": "crm",
      "version": 2,
      "active": false,
      "description": null,
      "definition": {},
      "enforced": false               // governed_by / source ABSENT
    }
  ]
}
```

**`governed_by` and `source` exist only when `enforced` is `true`.** Both must be optional in the
TypeScript type; treating them as always-present is a runtime crash on every non-governed rule.

### 3.2 New endpoints

**None.** Zero backend files touched — the second consecutive cookbook with no backend change.

### 3.3 CORS / middleware

No change. Everything goes through the Feature 0 proxy over `businessApi`.

---

## §4 — Findings

### G1 — `administrateur` is the highest role gate in the series so far

Every previous read surface was `superviseur` (advisors, coverage, tickets, sessions, callbacks).
This one is `administrateur`. From `security.py`: `_ROLE_RANK = {conseiller: 1, superviseur: 2,
administrateur: 3}`.

**A supervisor cannot see the guardrails at all.** This will not show up in development, because
the Feature 0 dev session defaults to `administrateur` and `BUSINESS_API_DEFAULT_ROLE` also
defaults to `administrateur`. It appears the first time a real supervisor logs in.

So:

- The `/policies` nav entry and route must be **hidden below `administrateur`**, not merely
  403-ing after navigation. Use the existing `hasRank` helper from Feature 0.
- The server function is gated with `requireRole("administrateur")` regardless — per the Feature 0
  doctrine that a route guard is UX, not an authorization boundary.
- Raised as §8.2: this may be intentional (thresholds are governance) or may be stricter than you
  want.

### G2 — `active` is a boolean; the mock passes a string to `StatusChip`

A new variant of the recurring chip trap — fifth appearance, first time it is a **type** mismatch
rather than a missing key.

The mock does `<StatusChip status={p.status} />` against a mock string. The real field is
`active: boolean`. `status.ts` has both `active` and `inactive`. So:

```ts
const ruleStatusKey = (active: boolean) => (active ? "active" : "inactive");
```

The failure mode to avoid is `String(rule.active)` → `"true"`, which is not a key in `status.ts`,
so `StatusChip` returns `null` and the column renders blank for **every row**. Both target keys
already exist, so no `status.ts` change — which keeps the zero-diff guarantee on that file intact
for the seventh cookbook running.

### G3 — `definition` is a variable-shape object; a single `Token` cannot represent it

The mock has one `Threshold` column holding `<Token>{p.threshold}</Token>` — a single scalar.

Reality:

| Rule | `definition` |
|---|---|
| `RULE_BILLING_CAP` | 1 key |
| `RULE_DEFERRAL_ELIGIBILITY` | **3 keys** |
| non-governed | arbitrary JSONB, frequently `{}` |

There is no scalar to put in the cell. Options considered:

- **Show only the first key.** Rejected — silently hides two of the three deferral thresholds.
  A guardrails page that hides guardrails is worse than no page.
- **Raw JSON in the cell.** Rejected — unreadable, and breaks the row height rhythm (`Td` is
  `h-[52px]`).
- **Render each key as its own `Token` pair.** ✅ Chosen.

Each entry renders as a humanised label plus a `Token` value, stacked. `max_payment_tnd` →
"Max payment" + `Token` `200 TND`. Empty `{}` → em-dash, never `{}` or `null`.

Because the deferral row is three lines, the table uses natural row height for this column rather
than forcing `h-[52px]` — achieved by letting the existing `Td` wrap its content, **not** by
introducing a new spacing token.

Unit humanisation is derived from the key suffix, which is consistent in the source:
`*_tnd` → ` TND`, `*_days` → ` days`, `*_per_year` → `/year`. Applied only to those suffixes;
unknown keys render the raw value with no invented unit.

### G4 — `enforced` is the honesty surface, and the whole reason this page is worth building

This is the finding that turns a table into something an operator can trust.

A governed rule's numbers are **live, read from the same env the engine reads**. A non-governed
rule's `definition_json` is a **seeded literal with no guaranteed relationship to enforcement**.
Rendering them identically would imply every number on the page is enforced — which is precisely
the drift `policy_view.py` was written to eliminate. Reintroducing that confusion in the UI would
defeat the module.

So:

- Governed rows show a small `Token` reading **`Enforced`**, plus `governed_by` env var names in
  `t-mono text-ink-4` beneath the thresholds. The env var name is the actionable fact — it tells
  you exactly what to change and where.
- Non-governed rows show **`Catalog`** in a muted `Token`.
- A `CardHeader` subtitle above the table states, once: *thresholds are enforced from `POLICY_*`
  environment variables, not from this registry; catalog rules are governance records only.*

No new colours — the distinction is carried by `Token`'s existing `strong` prop and `text-ink-*`
levels, both already in `primitives.tsx`.

### G5 — Removing "New policy", and why not "disabled"

Same reasoning as Feature 5's "New ticket", applied to a different cause. There the button had a
surprising side effect; here the capability cannot exist at all. Both resolve to removal.

A disabled button with a tooltip would still assert that creating a policy is a coherent action
that is merely unavailable right now. It is not coherent: a new row in `business_rules` would be
governance metadata for a rule the engine does not execute, and would enforce nothing. Offering it
later would require the policy engine to change first.

The caption in G4 replaces it and explains the model.

### G6 — `_num()` silently swallows malformed env values

```python
try:
    return int(raw) if isinstance(default, int) else float(raw)
except ValueError:
    # A malformed override should not crash the admin view; report the enforced default.
    return default
```

Correct for availability, but it has a consequence for this page: if someone sets
`POLICY_PAYMENT_CAP_TND=5OO` (letter O), the dashboard displays **200** — the default — with no
indication anything is wrong.

The dashboard **cannot detect this**; the raw string never crosses the wire. I am not inventing a
detection mechanism, and I am not adding a warning that would fire on healthy systems.

What the page *can* honestly do is name `governed_by` (G4), so an operator checking a suspicious
number knows precisely which variable to inspect. Logged as §8.4 — the real fix would be
`policy_view` reporting a parse failure, which is a backend change.

### G7 — The overlay is only truthful if both containers share the same env

> "both containers load the same `.env` via `env_file`"

The entire no-drift guarantee rests on that. If `business-api` and `policy-service` are ever
deployed with divergent environments, this page reports `business-api`'s view of the thresholds
while the engine enforces its own — recreating the exact drift the module exists to prevent, but
now with the dashboard's authority behind the wrong number.

Nothing in the frontend can detect or mitigate this. It is a deployment invariant. Recorded here
because a reader of this page must know its trust boundary, and raised as §8.5 — which is also
where the long-standing deployment-topology question from Cookbook 4 §8.2 finally becomes
load-bearing rather than merely tidy.

### G8 — `GOVERNED_BY` covers exactly two rule ids

If `policy-service` grows a third threshold and `GOVERNED_BY` is not extended, that rule appears
as `enforced: false` — shown as a catalog entry while actually being enforced. The failure is
silent and the dashboard would mislabel it.

A frontend cannot detect this either. Noted so that "add the rule to `GOVERNED_BY`" becomes part
of the checklist whenever a `POLICY_*` variable is added. §8.6.

### G9 — `rule_id` is unique: no duplicate-key hazard this time

Worth stating explicitly because Features 4, 5 and 6 all had one. `rule_id` carries a `unique=True`
constraint, so `key={rule.rule_id}` is safe. The mock's `key={p.name}` happens to be correct here
— the only mock in the series whose key survives contact with real data.

### G10 — No timestamps on the wire, and this time no substitute is needed

`BusinessRule` has the `Timestamps` mixin, but `business_rules()` projects neither field — the
same DTO-drops-the-timestamp situation as Feature 6's `DocumentSummary`.

Unlike Feature 6, **the mock has no "Updated" column here**, so nothing needs replacing. The mock's
four columns are Policy, Threshold, Version, Status — all four are backed by real data. No
column is dropped, and the two added columns (Domain, Enforcement) come from real fields.

### G11 — No pagination, and none needed

The registry is a governance catalog of a handful of rules, ordered `domain, rule_id`. Preserve
the server ordering; do not client-side re-sort (the Feature 6 F12 rule). Grouping by `domain` is
visually useful and free, since the server already orders by it — rendered as a subtle domain
label, not as new table-grouping machinery.

### G12 — `description` is nullable

`Text` nullable, and `null` in practice. Render the description beneath `rule_id` **only when
non-null and non-empty** — the same conditional-second-line rule established in Feature 6 F6, for
the same reason: a column of ragged blank second lines looks broken.

### G13 — `data.ts` removal: `POLICIES` only

`RULES` **stays** — `/rules` is untouched (§1). Only `POLICIES` is removed, and only after the
guarded grep established in Feature 4:

```bash
grep -rn "POLICIES\|RULES" src/
```

Beware a substring match: `POLICIES` may appear inside other identifiers. Confirm whole-symbol
imports before deleting, and leave `RULES` in place.

### G14 — No route or navigation change

`/policies` already exists in `routeTree.gen.ts`, `nav.ts` and `PAGE_META`. Rewritten in place.
The only nav-adjacent change is the `administrateur` visibility gate (G1), which uses the existing
`hasRank` helper and adds no new shortcut. `/rules` untouched.

---

## §5 — Frontend implementation plan

### 5.1 Files

| Action | Path |
|---|---|
| **new** | `src/lib/api/policies.server.ts` |
| **new** | `src/lib/nexus/policy-view.ts` |
| **modified** | `src/lib/nexus/query-keys.ts` — append `policyKeys` |
| **modified** | `src/lib/nexus/data.ts` — remove `POLICIES` only (G13) |
| **rewritten** | `src/routes/policies.tsx` |
| **untouched** | `src/routes/rules.tsx` — **zero diff** (§1) |

Zero-diff files: `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx`, `blocks.tsx`,
`modal.tsx`, `format.ts`, `styles.css`, `rules.tsx`, and all existing `src/lib/api/*`.

### 5.2 `src/lib/api/policies.server.ts`

Uses the Feature 0 substrate unchanged — no new transport this time (contrast Feature 6, which
needed `knowledgeApi` for a second service). Everything is `business-api` over the existing proxy.

```ts
export type PolicyRule = {
  rule_id: string;
  domain: string;
  version: number;
  active: boolean;
  description: string | null;
  definition: Record<string, number | string | boolean>;
  enforced: boolean;
  governed_by?: string[];   // present only when enforced
  source?: string;          // present only when enforced
};
```

`listPolicyRules` — `createServerFn({ method: "GET" })`, `requireRole("administrateur")`
(factory form, per the Feature 2 correction; copy the composition from `availability.server.ts`),
calling `businessApi<{ rules: PolicyRule[] }>("/api/v1/reference/business-rules", { role })`.

No query parameters at all — so the empty-filter convention that bit Cookbooks 3 and 5 in opposite
directions **does not apply here**. Nothing to omit, nothing to send blank. Worth stating plainly
since I flagged in Cookbook 6 that each cookbook must declare its convention explicitly: **Cookbook
7 sends no query parameters.**

### 5.3 `src/lib/nexus/policy-view.ts`

Pure, testable, no JSX, no network:

- `ruleStatusKey(active: boolean): StatusKey` — G2.
- `definitionEntries(def): Array<{ label: string; value: string }>` — G3, humanises keys and
  applies the three known unit suffixes.
- `thresholdLabel(key: string): string` — `max_payment_tnd` → `"Max payment"`.
- `thresholdValue(key, value): string` — suffix-driven units only.
- `enforcementLabel(rule): "Enforced" | "Catalog"`.
- `governedByList(rule): string[]` — returns `[]` when absent, never `undefined` (G/type safety).
- `ruleMatches(rule, query): boolean` — client-side search over `rule_id`, `description`, `domain`.
- `groupByDomain(rules): Array<{ domain: string; rules: PolicyRule[] }>` — preserves server order.

### 5.4 `query-keys.ts`

```ts
export const policyKeys = {
  all: ["policies"] as const,
  rules: () => [...policyKeys.all, "rules"] as const,
};
```

No invalidation anywhere — there are no mutations on this page.

### 5.5 `src/routes/policies.tsx`

One `PageSection`, one `TableShell`, preserving the mock's composition.

**Toolbar:** `SearchInput placeholder="Search policies" className="w-[260px]"` (client-side,
G13/5.3). **No `ml-auto` button** — removed per G5.

**Columns** — mock had `Policy | Threshold | Version | Status`:

| Column | Align | Source |
|---|---|---|
| Policy | left | `rule_id` in `t-mono text-ink-1`; `description` beneath in `t-caption text-ink-4` when non-empty (G12) |
| Domain | left | `domain`, `t-ui text-ink-2` |
| Thresholds | left | stacked label + `Token` pairs (G3); `—` when `{}` |
| Enforcement | left | `Enforced` / `Catalog` `Token`; `governed_by` env names beneath in `t-mono text-ink-4` (G4) |
| Version | right | `t-mono text-ink-3` — unchanged from mock |
| Status | left | `StatusChip status={ruleStatusKey(rule.active)}` (G2) |

Row: `key={rule.rule_id}` (G9), preserving
`className="transition-colors duration-[120ms] hover:bg-surface-3"`.

**States:**
- Loading → `TableSkeleton rows={6} cols={6}`.
- Error → `TableErrorRow`. On **403**, a specific message: the registry requires the administrator
  role — not the generic network error (the Feature 1 `errorMessage()` lesson, and G1 makes 403 a
  genuinely expected outcome here rather than an edge case).
- Empty (200, zero rules) → `EmptyState`. Distinct from error, per the Feature 6 F10 rule.

**Footer:** `{rules.length} policies` — mirroring the mock. Safe to compute client-side here
because, unlike Feature 6, there is no hide/show filter that could desynchronise it from a server
total; the only filter is search, and the footer reflects the filtered view intentionally.

**Header caption:** the `CardHeader` subtitle from G4, stating the enforcement model once.

### 5.6 Nav visibility

`/policies` is hidden for roles below `administrateur` using the existing `hasRank` helper and the
session from Feature 0. This is UX only — the server function's `requireRole` remains the actual
boundary.

---

## §6 — Design-system compliance

| Constraint | Status |
|---|---|
| New colours / spacing / radius / type tokens | none |
| New component shapes | none — `TableShell`, `Td`, `Th`, `Token`, `StatusChip`, `SearchInput`, `EmptyState`, `CardHeader` |
| New npm dependencies | **zero** |
| New `status.ts` keys | **zero** — `active`/`inactive` both exist |
| New routes / nav entries / shortcuts | **zero** |
| Backend changes | **zero** |
| Buttons added | **zero** (one removed) |
| Modals / overlays | none — no `.rise` containing-block risk this time |
| Lint baseline | must return to exactly **36 problems** |

---

## §7 — Validation checklist

**Static**

- [ ] `tsc --noEmit` clean — including that `governed_by`/`source` are optional (§3.1).
- [ ] `eslint` returns exactly the 36-problem baseline.
- [ ] `build` exit 0.
- [ ] `git diff --stat` shows **zero** backend files.
- [ ] `rules.tsx`, `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx` — all zero diff.
- [ ] `grep -rn "POLICIES" src/` → empty; `grep -rn "RULES" src/` → still present for `/rules`.
- [ ] No raw hex or `rgb(` introduced.

**Behavioural**

- [ ] Table renders; every row shows an `active` **or** `inactive` chip — no blank status
      cells (G2). *This is the specific regression to look for.*
- [ ] `RULE_DEFERRAL_ELIGIBILITY` shows **all three** thresholds, not just the first (G3).
- [ ] `RULE_BILLING_CAP` shows `Enforced` plus `POLICY_PAYMENT_CAP_TND` (G4).
- [ ] A non-governed rule shows `Catalog` and **no** env var line, with no crash from the absent
      `governed_by` (§3.1).
- [ ] A rule with `definition: {}` renders `—`, never `{}` or `null`.
- [ ] A rule with `description: null` renders no blank second line (G12).
- [ ] Search filters over rule id, description and domain.
- [ ] Rows appear grouped by domain in server order; no client re-sort (G11).
- [ ] **No "New policy" button anywhere on the page** (G5).

**Enforcement truthfulness** — the tests that actually validate the point of the page

- [ ] Set `POLICY_PAYMENT_CAP_TND=500`, restart `business-api`, reload: the page shows **500**,
      not the seeded literal and not the 200 default.
- [ ] Unset it, restart, reload: the page shows **200** (the pinned default).
- [ ] Set it to a malformed value (`5OO`): the page shows **200** with no error — confirming G6 is
      understood and expected, not a bug to chase.

**Roles**

- [ ] `administrateur`: page visible, data loads.
- [ ] `superviseur`: `/policies` **hidden from nav**; direct navigation yields the specific 403
      message, not a generic network error (G1).
- [ ] `conseiller`: same as supervisor.

**Network discipline**

- [ ] Zero direct browser requests to `:8108`.

---

## §8 — Open questions

**§8.1 — What should `/rules` become?** (§1 — the one I most need an answer on.)
It has no backend. Three honest options:

1. **Remove the route and its nav entry.** Cleanest. The dashboard stops advertising a capability
   the platform does not have.
2. **Leave it on mock data, clearly marked as a template placeholder.** Lowest effort; carries the
   risk that someone eventually believes it.
3. **Repurpose it as the policy verdict ledger** — real data, currently homeless. My recommendation,
   but it is precisely your *"Decisions and requested actions logs"* feature, so it belongs in
   Cookbook 8 under an accurate name rather than being retrofitted here.

If you actually want a trigger→action automation engine, that is a backend feature request, not
frontend wiring — and I will not build it under Rule 3.

**§8.2 — Is `administrateur` the right gate for viewing guardrails?** (G1)
Supervisors currently cannot see them. Defensible for governance data, but supervisors are the
people handling escalations against these limits. Widening to `superviseur` is a one-word change
in `main.py` — a backend change, so I did not make it.

**§8.3 — Should `version` and `active` be editable?**
These are the two fields that are *genuinely* writable without lying: neither is overlaid by
`overlay()`, and `active` is real governance state. But there is **no write endpoint**, and
deactivating a rule in the registry would **not** stop the engine enforcing it (the engine executes
in code) — so even this narrow edit would be a half-truth. I did not build it. Ask me if you want
the honest version scoped.

**§8.4 — Should `policy_view` report malformed `POLICY_*` values?** (G6)
Today a typo silently reads as the default. A `parse_error: true` flag alongside `enforced` would
make it visible. Small backend change; I did not take it unilaterally.

**§8.5 — Deployment topology.** (G7)
Do `business-api` and `policy-service` genuinely share one `env_file` in every environment? The
no-drift guarantee — and therefore this page's correctness — depends entirely on it. This finally
makes the Cookbook 4 §8.2 topology question load-bearing.

**§8.6 — Process note, not a question.** (G8)
Adding a `POLICY_*` threshold requires adding the rule id to `GOVERNED_BY`, or the registry will
mislabel an enforced rule as catalog-only. Worth putting in the policy-service checklist.

**§8.7 — Expose `updated_at` on business rules?** (G10)
Same two-line shape as Cookbook 6 §8.1. Not needed here (no column requires it), but if you take
the Feature 6 change, take both for consistency.

---

## §9 — Diff summary

```
 Frontend/admin_dashboard/
   src/lib/api/policies.server.ts   | new
   src/lib/nexus/policy-view.ts     | new
   src/lib/nexus/query-keys.ts      | +policyKeys
   src/lib/nexus/data.ts            | -POLICIES  (RULES kept)
   src/routes/policies.tsx          | rewritten
   src/routes/rules.tsx             | UNTOUCHED — flagged, see §1

 backend                            | 0 files changed
```

Zero new dependencies · zero new tokens · zero new status keys · zero route changes ·
zero nav changes · zero backend changes · zero CORS changes · zero mutations.

---

## §10 — Next feature

**Decisions & requested-actions logs** (§8.1 option 3's natural home).

Both halves are real and already have endpoints, both `superviseur`:

- `GET /api/v1/policy/verdicts?session_id=<uuid>` → `{verdicts: [{id, action, verdict, rule_id, justification}]}`
- `GET /api/v1/actions?status=failed` → `{actions: [{id, action_type, status, idempotency_key, reference}]}`

Two problems are already visible from the extraction I have done, and they will shape that cookbook:

1. **`session_id` is a required query parameter on `/policy/verdicts`** — there is no
   estate-wide verdict list. Structurally the same wall as Feature 5's `lookup_tickets`
   (per-customer only). Either the page is driven from a session chosen elsewhere, or it needs a
   new backend read. `PolicyVerdict` also carries `direction`, `customer_id`, `inputs_snapshot` and
   `created_at`, **none of which `verdicts()` projects** — so a richer view means touching the
   repository.
2. **`/actions` defaults to `status="failed"`** and `ActionLedger`'s full status vocabulary is not
   yet confirmed — so the "All" scope is another instance of the empty-filter convention question
   that Cookbooks 3 and 5 answered in opposite directions.

Reads required: `persistence/models/execution.py` (`4ef95332`), `telemetry_timeline` consumers, and
the `/rules` + `/conversations` mocks (`44a50614`, `99ead9ea`) to decide the §8.1 landing site.
