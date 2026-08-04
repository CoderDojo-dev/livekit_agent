# Master Apply Runbook — Cookbooks 3 → 14

**Branch of truth:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Apply onto:** local `version_80` (currently HEAD `eda5f58`, Features 0/1/2 applied, **not pushed, not merged**)
**Status:** Features 0, 1, 2 = **APPLIED**. Cookbooks 3–14 = **designed, unapplied**.

This document is not a new feature. It is the ordering, collision and regression contract for landing twelve designs that were each written in isolation and that touch the **same eight files**. Applying them in cookbook-number order will break the build. Applying them in the order below will not.

---

## 0. Read this first — four corrections that outrank the cookbooks

These were discovered *after* the cookbooks that contain them were written. **Where a cookbook and this section disagree, this section wins.**

### C-1. Cookbook 4's headline bug is mis-diagnosed — do not apply its null guard

C4 §8.7 diagnoses a 500 in `session_detail` at `float(call.max_frustration_score)` and prescribes a null guard. Cookbook 13's read of `conversation.py` (`ec4592ad`) proved the column is:

```python
max_frustration_score: Mapped[float] = mapped_column(
    Numeric(5, 2), nullable=False, server_default=text("0"))
```

`NOT NULL DEFAULT 0` — it cannot be `None`. **Skip the C4 §8.7 guard.** Instead run this once before applying C4:

```sql
SELECT count(*) FROM conversation.call_sessions WHERE max_frustration_score IS NULL;
```

Expected `0`. A non-zero result means a migration added the column without backfilling and the model lies about the live schema — stop and tell me, because that changes C4 **and** C9's KPI math. Note `kpis()` uses `coalesce` and `telemetry_timeline()` uses `or 0.0`; that defensive coding suggests the authors were unsure, but the schema is authoritative.

**Also revise C8 §8.6**, which repeats the same wrong premise.

### C-2. Cookbook 10 ships with a known defect — fix it during apply, not after

C10 contains three `toLocaleString("en-US")` call sites. They must be `formatInteger` from `format.ts`. Nothing else in the console formats numbers inline, and `LOCALE` is centralised there. Fix at apply time; do not land it and file it.

### C-3. `/rules` was never a duplicate of `/policies`

C7 §8.1 and C13 §8.6 both recommend retiring `/rules` as redundant. **That recommendation is withdrawn.** C14 §0.1 establishes it was a UI for a non-existent automation engine, and repurposes the slot into `/reference`. Follow C14; ignore the earlier retirement notes.

### C-4. The `data.ts` deletion blocker is cleared

C9 and C11 both hedged on deleting mock exports because an unread `index.tsx` might import them. `index.tsx` (`419e7d34`) is a seven-line bare redirect to `/overview` with **zero imports**. All mock deletions in this runbook are safe.

---

## 1. The one hard ordering constraint

**C9 modifies `src/components/nexus/blocks.tsx` to make `delta` optional (`delta?`). C11 and C12 render stat cards without a delta. Neither compiles until C9 lands.**

This is the only true compile-level dependency in the set. Everything else is a merge-conflict risk, not a build break — but the ordering below minimises both.

---

## 2. Apply order (strict)

| # | Cookbook | Why here | Backend? |
|---|---|---|---|
| 1 | **C9** KPIs & Analytics | unblocks `blocks.tsx` `delta?` for C11/C12; strips the fabricated `status` server-side | **+2** |
| 2 | **C4** Call logs & transcripts | the session detail that C11 and C13 cross-link into | **+2** |
| 3 | **C11** Customers & 360 | needs C9; provides `?search=` that C3's manual booking wants | **+2** |
| 4 | **C3** Callbacks | consumes C11's customer search | 0 |
| 5 | **C5** Tickets | independent; verify no new route before applying | 0 |
| 6 | **C6** Knowledge / RAG | independent; talks to `:8102`, not business-api | 0 |
| 7 | **C7** Guardrails & Policies | independent; read-only over an existing route | 0 |
| 8 | **C8** Decisions & actions | independent | **+2** |
| 9 | **C10** Audit, integrity, retention | apply **with** correction C-2 | **+2** |
| 10 | **C12** Agents management | needs C9 | **+2** |
| 11 | **C13** Escalations & handoff | needs C4 (session cross-link) | 0 |
| 12 | **C14** Reference catalogs | last; retires `/rules` | **+2** |

"**+2**" = one repository method + one route.

**Land each cookbook as its own commit on `version_80`.** Twelve commits, each independently revertable. Do not squash — if a regression appears at step 9 you need to bisect to one cookbook, not one mega-diff.

---

## 3. Shared-file collision map

These eight files are touched by multiple cookbooks. Every one is an append or an in-place replace — **no cookbook reorders another's work.**

### 3.1 `apps/business-api/src/business_api/main.py` — six new routes

Route order matters **once**, and only once:

> **C11's `GET /api/v1/customers` MUST be registered BEFORE the existing `GET /api/v1/customers/{customer_id}/360`.** FastAPI matches in declaration order; a literal-vs-parameter ambiguity here is a live 404/422 bug.

Every other addition is a distinct literal path with no ambiguity:

| Cookbook | Route | Role | Placement |
|---|---|---|---|
| C11 | `GET /api/v1/customers` | Conseiller | **before** `/customers/{id}/360` |
| C4 | `GET /api/v1/sessions` | Conseiller | before `/sessions/{session_id}` (same literal-vs-param rule) |
| C8 | `GET /api/v1/decisions` | Superviseur | after `/policy/verdicts` |
| C9 | `GET /api/v1/analytics/trend` | Superviseur | after `/telemetry/timeline` |
| C10 | `GET /api/v1/audit/entries` | Administrateur | after `/audit/verify` |
| C12 | `GET /api/v1/agents/activity` | Superviseur | after `/telemetry/timeline` |
| C14 | `GET /api/v1/reference/catalogs/{catalog}` | Administrateur | after `/reference/business-rules` |

**Both literal-before-parameter rules (C11 and C4) are the highest-risk lines in the entire twelve-cookbook set.** Verify with Check G-7.

### 3.2 `repositories.py` — six new methods

`session_list` (C4), `decision_ledger` (C8), `analytics_trend` (C9), `audit_entries` (C10), `customer_list` (C11), `agent_activity` (C12), `reference_catalog` (C14). All are additive methods on `SupervisionRepository`; none modifies an existing one. The class docstring — *"Read-side queries… Read-only; never mutates audit"* — stays true of all seven.

**Import watch:** the file does **not** import `os`. C9's `analytics_trend` needs it. C14 extends the existing `from persistence.models.reference import BusinessRule` line. Merge the import block once, at the end, rather than per-cookbook.

### 3.3 `src/lib/nexus/data.ts` — mock deletions

Delete only in the cookbook that owns each export, and only after its route stops importing it:

| Cookbook | Removes |
|---|---|
| C9 | `OVERVIEW_STATS`, `CALL_VOLUME_SERIES`, `RESOLUTION_SERIES`, `HERO_SPARKLINE`, `BILLING_ACTIVITY`, `ADVISOR_TEAM` |
| C10 | `SETTINGS_SECTIONS` |
| C11 | `CustomerRow`, `CUSTOMERS` |
| C13 | `ConversationRow`, `CONVERSATIONS`, `Bubble`, `THREAD` |
| C14 | `RULES` |

**`INGESTED_FILES` — grep before touching.** C13 removes the ingestion panel from `/conversations`, but C6's `/knowledge` may still reference it. `grep -rn "INGESTED_FILES" src/` must return zero hits before deletion. This is the single most likely accidental build break in the set.

### 3.4 `src/lib/nexus/nav.ts` — shortcut registry

Already taken: **`G A`** Advisors (C1) · **`G D`** Availability (C2).
Added: **`G K`** Decisions (C8) · **`G G`** Agents (C12) · **`G E`** Escalations (C13) · **`G R`** Reference (C14).

No collisions. C13 and C14 **rename in place** (`/conversations`→`/escalations`, `/rules`→`/reference`) — same section, same position. Update `PAGE_META` in the same edit; a stale `PAGE_META` key renders an empty page header, which is silent.

### 3.5 `routeTree.gen.ts`

Generated. **Do not hand-edit and do not merge it per-cookbook.** Let the dev server regenerate after each route add/rename/delete, and commit the regenerated file with that cookbook's commit. Feature 1 proved a stale tree is invisible until navigation fails at runtime.

### 3.6 `src/lib/nexus/query-keys.ts`

Pure appends: `analyticsKeys` (C9), `auditKeys` (C10), `customerKeys` (C11), `agentKeys` (C12), `escalationKeys` (C13), `referenceKeys` (C14). No conflicts.

### 3.7 `src/components/nexus/blocks.tsx`

**C9 only.** One change: `delta` → `delta?`. Nothing else in the set touches this file. See §1.

### 3.8 `src/lib/nexus/status.ts`

**Zero changes. Twelve consecutive cookbooks.** Every backend vocabulary is mapped in a `*-view.ts` helper instead. This is a **global invariant**, not a preference — `git diff -- src/lib/nexus/status.ts` must be empty after all twelve commits. If a cookbook seems to need a new chip, the mapping is wrong, not the truth table.

---

## 4. Hazard register — things that can cause real damage

### H-1. Retention job has no floor — **do not expose the input without it**

`POST /api/v1/jobs/retention` accepts `retention_days` with **no lower bound**. `0` or a negative value matches every session and, with `dry_run=false`, permanently overwrites every `Turn.transcript_masked` with `"[purged]"` and deletes every audio blob. **There is no undo.**

C10 ships the two-phase typed confirmation and drafted a floor but did **not** ship the backend clamp. **Decision required before C10 lands.** My recommendation: clamp server-side to a minimum of 30 days and reject anything lower with a 422. One line, and it makes the catastrophic case unreachable rather than merely inconvenient.

### H-2. Never run destructive SQL against the dev database

During Feature 1's test harness, `advisor_shifts` was truncated from 34 rows to 10 by a `CREATE TABLE tmp AS SELECT …` + `DROP` pattern. It was reconstructed to 33 rows and proven equivalent to the v73 audit — **the 34th row is permanently lost.**

For all twelve cookbooks: seed with `INSERT`, assert with `SELECT`, clean up with targeted `DELETE`. **No `DROP`, no `TRUNCATE`, no table swaps.** Take a `pg_dump` before starting.

### H-3. Ticket writes are silently reverted

C5 F3: anything the dashboard writes to `ticketing.tickets` is overwritten by the next `upsert_from_glpi()` sync. C5 ships read-only for exactly this reason. Do not "improve" it by adding a write during apply.

### H-4. `require_internal_key` is opt-in — C6 will pass locally and 403 in any environment where `INTERNAL_API_KEY` is set

Test C6 **with the key set**, not just with a bare local knowledge-service. This is a dev/prod divergence that unit tests cannot catch.

### H-5. `customer_360` has no UUID validation

A malformed id yields **500, not 404**. C11 documents it; the guard is drafted, unshipped. Either ship the guard with C11 or accept that a bad link surfaces as a server error.

---

## 5. Per-cookbook gate

No cookbook is "done" until **all** of these pass. Run them at each of the twelve commits, not once at the end.

1. `bunx tsc --noEmit` → clean.
2. `bun run lint` → **exactly 36 problems** (28 prettier errors + 8 warnings). This is the frozen baseline. Not 35, not 37.
3. `bun run build` → exit 0.
4. `git diff -- src/lib/nexus/status.ts` → empty.
5. `git diff --stat -- Frontend/admin_dashboard/package.json` → empty. **Zero new dependencies across all twelve.**
6. `git diff --stat -- apps/ packages/` → for a 0-backend cookbook, empty; for a +2, exactly `repositories.py` and `main.py`.
7. Network tab → **zero direct requests to `:8108`**. All traffic proxies through the TanStack server (the topology you chose in Feature 0). C6 is the one exception: it talks to `:8102`, also server-side.
8. Colour scan on new files → `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}'` → no hits. The design bible is achromatic by law: every hex satisfies `RR === GG === BB`.
9. Date-trap scan → `grep -n 'getDay(\|getHours(\|new Date(\|toLocaleString('` → no hits in new files.
10. Every new overlay/fixed element portals to `document.body`. `PageSection` carries `.rise` (`transform: translateY(8px)`), which creates a containing block and **clips any `position: fixed` child**. This cost us a real defect in Feature 1.
11. Role gates verified by `curl` at the boundary: correct role → 200, one rank below → 403.
12. Every status chip renders **non-blank** for every backend value — seed one row per vocabulary value and look. `StatusChip` returns `null` for unmapped keys, so a mapping bug is an *invisible* cell, not an error. **This trap has recurred twelve times.**

---

## 6. Global regression pass (after all twelve)

1. Every nav entry resolves; no 404s. Walk all sixteen routes.
2. Every keyboard shortcut fires the right route: `G A`, `G D`, `G K`, `G G`, `G E`, `G R`.
3. `grep -rn "nexus/data" src/routes/` → only routes that still legitimately use mocks.
4. `grep -rn "/rules\|/conversations" src/` → zero hits (both renamed).
5. Log in as each of `conseiller`, `superviseur`, `administrateur` and walk every route. Forbidden pages must show the substrate's forbidden state — **not a crash, not an infinite retry**. QueryClient retries `false` on 401/403.
6. Kill business-api, reload every page → each shows its error state with a working retry. No white screens.
7. Empty database → every page shows its `EmptyState`, no `NaN`, no `—` where a zero belongs, no chart crash. `LineChart` **breaks on 0 or 1 points** — C9's `isChartable` guard must hold.
8. `pg_dump` diff before/after the full pass → only rows you deliberately seeded. **No read-only cookbook may have written anything.**

---

## 7. Rollback

Twelve independent commits on `version_80`, nothing pushed. `git revert <sha>` per cookbook. The only cross-cookbook revert hazard is **C9**: reverting it after C11/C12 have landed re-breaks `blocks.tsx` and those two stop compiling. Revert C12 and C11 first, or re-apply the one-line `delta?` change by hand.

Backend reverts are clean — every addition is a new method and a new route; nothing existing was modified.

---

## 8. Decisions I still need from you

Ordered by how much they block.

1. **H-1 retention floor** — clamp to 30 days server-side? *Blocks C10.* Recommend yes.
2. **C-1 SQL check** — run the `max_frustration_score IS NULL` count and tell me the number. *Blocks C4.*
3. **H-5 UUID guard** — ship it with C11 or accept 500s on malformed ids?
4. **C14 §6.5 role** — should `superviseur` be able to read the error/plan catalogs, or is `administrateur` right?
5. **Feature 0 §8.1 — there is no user store anywhere in the backend.** Admin auth is currently a single env-var credential pair. Escalated by C10 §8.3 and C11 §0.3 and still unanswered. Real multi-user admin auth is a feature, not a config change.
6. **C9 §8.1 service health** — `system_overview()` reports eleven services as `"online"` **hardcoded**. C9 strips the fabricated status rather than display a lie. Real probes need a fan-out to eleven `/health` endpoints — new business logic, own cookbook, needs approval.

---

## 9. Still unexposed after all fourteen cookbooks

For completeness — modelled, real, and with no admin surface. None is a gap I invented work to fill; each needs your call on whether it matters.

- `CustomerInteraction`, `Payment`, `PaymentPlan`, `ConsentRecord` (C11 §8.6) — modelled CRM/billing data, no endpoint.
- `CallbackSchedule` lifecycle fields (`attempts`, `outcome_note`, `completed_at`, `assigned_advisor_id`) — C3 surfaces the schedule, not the outcome. The model comment argues these are the point: *"Without these a scheduled callback is a promise nobody can prove was kept."*
- `reference.geo_aliases` (C14 §6.3) — deliberately unexposed; a resolver probe beats a 10k-row table.
- The automation engine `/rules` implied (C14 §6.1) — does not exist; unbuilt by design.

---

## 10. Outstanding verification debt

Things I flagged and could not close from the repo alone:

- **C12 §8.1** — `server.py`'s `conversation_item_added` handler was not re-read, so whether **agent** turns carry `active_agent` is narrowed but unconfirmed. Affects the "Attributed turns" metric only.
- **`formatPercent`** (C9 G15) — its 0–1 vs 0–100 contract is unverified. C9 ships its own `formatRatio` rather than guess. Confirm before reusing `formatPercent` anywhere.
- **`persistence/base.py`** — unread; the `SoftDelete` column name (C11 F8) is unconfirmed.
- **`open_invoices.amount`** (C11 F7) — `customer_360` uses `float(i.total_amount)`, so a "Total outstanding" label would actually show **total invoiced**. C11 labels it accordingly; worth a second look at apply time.
- **Phase 2** — still awaiting the reproduction log, the in-flight tool name, and `pip show livekit-agents`. Asked 3 Aug 17:39; not re-asking.
