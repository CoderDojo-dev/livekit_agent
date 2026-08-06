# FEATURE_15 — Callback lifecycle evidence

> Branch of truth: `version_81` (head `2f10a071fc98f88a5d358b4a0a0352ad7b84bc8b`).
> Precedence chain honoured: `BATCH_1_APPLY` > `RUNBOOK_V2_CORRECTIONS` > `MASTER_APPLY_RUNBOOK` > `FEATURE_NN` > prior notes.
> Every file quoted below was read at that commit. No signature, class name or field in this document is inferred.

---

## 1. Feature name & scope

**Callback lifecycle surfacing** — making a scheduled callback *provable*: when it was honoured, what happened on it, how many attempts it took, and which call created the promise.

**In scope:** the `/callbacks` page only. One new read-only detail modal, one modified action cell.

**Out of scope:** slot booking, claiming, the `/availability` grid, and every write path (already applied in Feature 03). The client/customer portal is untouched.

**Backend work required: none.** This is a pure frontend cookbook. Decision **D11** ("callback lifecycle fields already exposed by `to_dict()`; the gap is UI-only") holds, and it is re-verified field by field in §2.

---

## 2. Backend reference (verified, unchanged)

| Path | What it gives us |
| --- | --- |
| `apps/business-api/src/business_api/callbacks.py` → `to_dict()` (lines 47–74) | Already serialises **every** lifecycle field: `attempts`, `outcome_note`, `completed_at`, `assigned_advisor_id`, `assigned_advisor_name`, `session_id`, `overdue`, `priority_level` |
| `callbacks.py` → `list_callbacks()` | `ORDER BY priority_level DESC, scheduled_time ASC`; optional `status` / `overdue_only`; `limit` |
| `callbacks.py` → `_hydrate()` | Joins `Customer` and `Advisor` so the queue is actionable without extra lookups |
| `callbacks.py` → `complete_callback()` | `reached=True` → `status='completed'` + `completed_at` stamped. `reached=False` → stays `pending`, clears `assigned_advisor_id`, **does not** touch `attempts` |
| `callbacks.py` → `cancel_callback()` | `status='cancelled'`, and writes its note into the **same `outcome_note` column** |
| `callbacks.py` → `claim_next()` | The **only** writer of `row.attempts += 1` |
| `packages/persistence/src/persistence/models/conversation.py` → `CallbackSchedule` | `CheckConstraint("status IN ('pending','completed','cancelled')", name="status")` |

**Conclusion of EXTRACT.** The backend hides nothing. `MASTER_APPLY_RUNBOOK` §9 lists `attempts` / `outcome_note` / `completed_at` / `assigned_advisor_id` as unexposed, but that entry is stale for the *transport* layer: `to_dict()` returns all four and `callbacks.server.ts` types all four. The gap is **purely in the render layer**. No endpoint, no CORS, no middleware change.

---

## 3. Endpoints

### 3.1 Existing, reused as-is

| Method | Path | Role | Notes |
| --- | --- | --- | --- |
| GET | `/api/v1/callbacks?status=&overdue_only=&limit=` | `conseiller` | Already called by `listCallbacks`. `status=""` is the only way to list all statuses (`if status:` guard in `list_callbacks`). |
| GET | `/api/v1/callbacks/stats` | `superviseur` | Already called by `getCallbackStats`. |
| GET | `/api/v1/advisors/coverage?days=1` | `superviseur` | Already called for `timezone`; shared cache key `availabilityKeys.coverage(1)`. |

Response envelope for the list endpoint is `{"callbacks": [...]}`; `listCallbacks` already unwraps it with `result.callbacks ?? []`.

One row, as typed in `callbacks.server.ts`:

```ts
export type Callback = {
  id: string;
  status: string;
  scheduled_time: string | null;
  preferred_window: string | null;
  reason: string | null;
  priority_level: number;
  attempts: number;
  outcome_note: string | null;
  completed_at: string | null;
  overdue: boolean;
  customer_id: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  assigned_advisor_id: string | null;
  assigned_advisor_name: string | null;
  session_id: string | null;
};
```

### 3.2 New endpoints to create

**None.** No file under `apps/`, `packages/` or `services/` is touched by this cookbook.

### 3.3 CORS / middleware

**No change.** `main.py` already sends:

```py
allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(",")
allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"]
allow_headers=["Content-Type", "X-Role"]
```

and the browser never talks to `:8108` directly — every call goes through a TanStack server function, where `business-api.ts` is the sole injector of `X-Role`.

---

## 4. Frontend implementation plan

### 4.1 AUDIT — what `/callbacks` renders today

`Frontend/admin_dashboard/src/routes/callbacks.tsx` renders 8 columns:

`Caller · Scheduled · Window · Reason · Advisor · Attempts · Status · (actions)`

Verified defects:

1. **`outcome_note` is fetched and searched but never displayed.** It is in the `callbackMatches` haystack (`callback-view.ts`), so today you can *search* for note text and get a hit whose note is invisible. A completed callback shows zero evidence of what was said.
2. **`completed_at` is fetched and never displayed.** A completed row shows only its *scheduled* time, so you cannot tell whether the promise was kept on time or three days late.
3. **`session_id` is fetched and never displayed**, even though `/calls` already accepts `?session=<uuid>` (`calls.tsx` `validateSearch` with `.catch({ session: undefined })`). The call that created the promise is unreachable from the promise.
4. **Terminal rows are inert dead ends.** The action cell renders only when `row.status === "pending"`, so the whole Completed and Cancelled scopes have nothing to click.

No mock data remains on this page. This is a *render* gap, not a wiring gap.

### 4.2 GAP ANALYSIS

| Side | Gap | Action |
| --- | --- | --- |
| Backend endpoints | none | — |
| CORS / middleware | none | — |
| Frontend component | no detail view for a callback | **create** `callback-lifecycle.tsx` |
| Frontend states | loading / error already handled by `TableSkeleton` + `TableErrorRow`; the modal renders data already in the list cache | **no new loading or error state** |
| Frontend empty | per-field empties follow the existing `t-caption text-ink-5` + `\u2014` convention | in-component |
| Query keys | no new query | **no `query-keys.ts` change** |
| `callback-view.ts` | `formatBusinessTime`, `callbackStatusKey`, `callbackCustomer`, `priorityLabel` all already exported | **zero changes** |

### 4.3 DECIDE — four explicit decisions

**D15.1 — A modal, not new table columns.** The table is already at 8 columns. `outcome_note` is free text up to 500 chars and would destroy row density. Detail modals are the established pattern for exactly this (`decision-detail.tsx`, `customer-detail.tsx`, `agent-detail.tsx`). Chosen: modal.

**D15.2 — Reuse `decision-detail.tsx`'s layout verbatim.** Its local `Row` (lines 7–15) is this codebase's label/value pattern. It is **not exported**, so it is copied byte-identically into the new file rather than exported from the old one. Rationale: adding a second export to `decision-detail.tsx` risks a new `react-refresh/only-export-components` finding, and the gate requires the non-prettier lint count to stay **exactly 9**. A local copy is the drift-free choice.

**D15.3 — No lateness arithmetic.** `scheduled_time` and `completed_at` are shown side by side and the reader compares them. `format.ts` has no coarse-interval formatter (`formatDuration` is `mm:ss`, seconds-based), and inventing one would be new behaviour rather than exposure of existing data. Explicitly declined.

**D15.4 — The session link is unconditional.** `decisions.tsx` passes `showCallLink={true}` hardcoded (comment G7), so the prop is vestigial. The link is rendered directly, using the exact anchor class string from `decision-detail.tsx`. No new tokens.

**Honesty note carried into the UI.** `attempts` is incremented **only** by `claim_next()` (`POST /api/v1/callbacks/claim`), which no admin screen calls. A callback completed straight from this table therefore legitimately shows `0 attempts`. Rather than hide that, the modal states it. This is the "no silent assumptions" rule applied to a counter that would otherwise look broken.

### 4.4 NEW FILE — `Frontend/admin_dashboard/src/components/nexus/callback-lifecycle.tsx`

```tsx
import { Modal } from "@/components/nexus/modal";
import { StatusChip, Token } from "@/components/nexus/primitives";
import {
  callbackCustomer,
  callbackStatusKey,
  formatBusinessTime,
  priorityLabel,
} from "@/lib/nexus/callback-view";
import type { Callback } from "@/lib/api/callbacks.server";

/** Byte-identical copy of decision-detail.tsx:7-15. Not imported because it is a local there,
 *  and exporting it would add a second export to a component module (lint baseline is fixed). */
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-sp-5 py-sp-4 first:pt-0 last:pb-0">
      <span className="t-label shrink-0 text-ink-3">{label}</span>
      <span className="min-w-0 flex-1 text-right">{children}</span>
    </div>
  );
}

type Props = {
  callback: Callback | null;
  timeZone: string;
  onClose: () => void;
};

/**
 * Read-only lifecycle record for one callback.
 *
 * Every field here already ships from callbacks.py::to_dict() and is already typed in
 * callbacks.server.ts — nothing new is fetched, so there is no loading or error state to
 * render. The modal exists because `outcome_note`, `completed_at` and `session_id` were
 * transported and then thrown away by the table (F15 gap analysis).
 */
export function CallbackLifecycleModal({ callback, timeZone, onClose }: Props) {
  if (!callback) return null;

  const customer = callbackCustomer(callback);
  const priority = priorityLabel(callback.priority_level);
  // cancel_callback() writes its reason into the SAME outcome_note column, so the label
  // must follow the status or a cancellation reason would be mislabelled as an outcome.
  const noteLabel = callback.status === "cancelled" ? "Cancellation reason" : "Outcome note";

  return (
    <Modal
      open
      onClose={onClose}
      title="Callback record"
      description={`${customer.name} \u00b7 ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
    >
      {/* Header strip — same construction as customer-detail.tsx */}
      <div className="flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle pb-sp-5">
        <StatusChip status={callbackStatusKey(callback)} />
        {priority ? <Token strong>{priority}</Token> : null}
        <Token>
          {callback.attempts} attempt{callback.attempts === 1 ? "" : "s"}
        </Token>
        <span className="t-caption ml-auto text-ink-4">{customer.phone}</span>
      </div>

      <div className="mt-sp-6 flex flex-col divide-y divide-stroke-subtle">
        <Row label="Scheduled">
          <span className="t-mono text-ink-1">
            {formatBusinessTime(callback.scheduled_time, timeZone)}
          </span>
        </Row>

        <Row label="Completed">
          {callback.completed_at ? (
            <span className="t-mono text-ink-1">
              {formatBusinessTime(callback.completed_at, timeZone)}
            </span>
          ) : (
            <span className="t-caption text-ink-5">
              {callback.status === "pending" ? "Still pending" : "Never completed"}
            </span>
          )}
        </Row>

        <Row label="Preferred window">
          {callback.preferred_window ? (
            <Token>{callback.preferred_window}</Token>
          ) : (
            <span className="t-caption text-ink-5">{"\u2014"}</span>
          )}
        </Row>

        <Row label="Reason">
          {callback.reason ? (
            <p className="t-ui text-left text-ink-2">{callback.reason}</p>
          ) : (
            <span className="t-caption text-ink-5">{"\u2014"}</span>
          )}
        </Row>

        <Row label="Advisor">
          {callback.assigned_advisor_name ? (
            <span className="t-ui text-ink-1">{callback.assigned_advisor_name}</span>
          ) : (
            <span className="t-caption text-ink-5">Unassigned</span>
          )}
        </Row>

        <Row label={noteLabel}>
          {callback.outcome_note ? (
            <p className="t-ui text-left text-ink-2">{callback.outcome_note}</p>
          ) : (
            <span className="t-caption text-ink-5">No note recorded.</span>
          )}
        </Row>

        <Row label="Originating call">
          {callback.session_id ? (
            <a
              className="t-mono break-all text-ink-1 underline decoration-dotted decoration-from-font underline-offset-4 hover:text-ink-4"
              href={`/calls?session=${encodeURIComponent(callback.session_id)}`}
            >
              {callback.session_id}
            </a>
          ) : (
            <span className="t-caption text-ink-5">Not linked to a session</span>
          )}
        </Row>

        <Row label="Callback ID">
          <span className="t-mono break-all text-ink-2">{callback.id}</span>
        </Row>
      </div>

      {callback.attempts === 0 ? (
        <p className="t-caption mt-sp-6 text-ink-5">
          Attempts are counted when an advisor claims a callback from the queue, so one handled
          directly from this table can close with none recorded.
        </p>
      ) : null}
    </Modal>
  );
}
```

**Design-system provenance of every class used above**

| Class string | Copied from |
| --- | --- |
| `flex items-start justify-between gap-sp-5 py-sp-4 first:pt-0 last:pb-0` | `decision-detail.tsx:9` |
| `t-label shrink-0 text-ink-3` / `min-w-0 flex-1 text-right` | `decision-detail.tsx:10-11` |
| `flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle pb-sp-5` | `customer-detail.tsx` header strip |
| `flex flex-col divide-y divide-stroke-subtle` | `decision-detail.tsx:48` |
| `t-mono break-all text-ink-1 underline decoration-dotted decoration-from-font underline-offset-4 hover:text-ink-4` | `decision-detail.tsx:57-58` |
| `t-caption text-ink-5` / `t-caption text-ink-4` / `t-ui text-ink-1` / `t-ui text-left text-ink-2` | `callbacks.tsx`, `callback-outcome.tsx`, `decision-detail.tsx` |
| `<Token>{n} attempt{…}</Token>` | `callback-outcome.tsx:78-80` |

Zero new colours, radii, spacings, shadows or type classes. No hex or `rgb()` literal. No `getDay`, `getHours` or `toLocaleString` — the only `new Date` in the path lives inside the pre-existing `formatBusinessTime`.

### 4.5 MODIFIED — `Frontend/admin_dashboard/src/routes/callbacks.tsx`

**Edit 1 — add the import**, immediately after the existing `callback-outcome` import:

```tsx
import { CallbackCancelModal, CallbackOutcomeModal } from "@/components/nexus/callback-outcome";
import { CallbackLifecycleModal } from "@/components/nexus/callback-lifecycle";
```

**Edit 2 — add one state hook**, after `cancelFor`:

```tsx
  const [cancelFor, setCancelFor] = useState<Callback | null>(null);
  const [detailFor, setDetailFor] = useState<Callback | null>(null);
```

**Edit 3 — replace the action `<Td>`** (the final cell inside the row map).

Before:

```tsx
                <Td>
                  {row.status === "pending" ? (
                    <div className="flex items-center justify-end gap-sp-3 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
                      <Button size="sm" variant="secondary" onClick={() => setOutcomeFor(row)}>
                        Outcome
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setCancelFor(row)}>
                        Cancel
                      </Button>
                    </div>
                  ) : null}
                </Td>
```

After:

```tsx
                <Td>
                  <div className="flex items-center justify-end gap-sp-3 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
                    <Button size="sm" variant="ghost" onClick={() => setDetailFor(row)}>
                      Detail
                    </Button>
                    {row.status === "pending" ? (
                      <>
                        <Button size="sm" variant="secondary" onClick={() => setOutcomeFor(row)}>
                          Outcome
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setCancelFor(row)}>
                          Cancel
                        </Button>
                      </>
                    ) : null}
                  </div>
                </Td>
```

The hover-reveal wrapper, gap, transition duration and button variants are unchanged — only the condition moved inward so terminal rows also get an affordance. `COLUMN_COUNT` stays `8`; the header is untouched.

**Edit 4 — mount the modal.** After the existing `cancelFor` block, before `</PageSection>`:

```tsx
      <CallbackLifecycleModal
        callback={detailFor}
        timeZone={timeZone}
        onClose={() => setDetailFor(null)}
      />
```

Passed unconditionally (the component self-guards on `null`), matching how `decisions.tsx` mounts `DecisionDetail`.

### 4.6 Data flow and states

| State | Behaviour |
| --- | --- |
| Loading | Unchanged — `TableSkeleton columns={8} rows={6}`. The modal opens from cached row data, so it has no loading state by construction. |
| Empty (no rows) | Unchanged — `EmptyState icon={PhoneOff}`. |
| Error | Unchanged — `TableErrorRow columns={8}` with retry. |
| Success | Row → `setDetailFor(row)` → modal reads the same `Callback` object. No refetch, no new cache entry, no invalidation. |
| Per-field empty | `preferred_window` / `reason` → `\u2014`; `outcome_note` → "No note recorded."; `completed_at` → "Still pending" or "Never completed"; `session_id` → "Not linked to a session"; `assigned_advisor_name` → "Unassigned". Every branch renders something. |
| Status chip | `callbackStatusKey` maps `pending`→`pending`/`overdue`, `completed`→`resolved`, `cancelled`→`closed`. All four are real `status.ts` keys, so the chip is never blank. |
| Timezone unknown | `timeZone` falls back to `"UTC"` exactly as the table does, and the page banner already discloses it. |

---

## 5. Validation checklist

### End-to-end functionality

1. `/callbacks` → **Completed** scope → hover a row → **Detail** appears → click → modal shows a real `completed_at` and the real `outcome_note` written by `complete_callback()`.
2. **Cancelled** scope → the note row is labelled **Cancellation reason**.
3. **Pending** scope → Detail · Outcome · Cancel all present. Record an outcome with "No answer — return to queue", reopen Detail → advisor now reads **Unassigned** (proves `complete_callback` cleared `assigned_advisor_id`).
4. Click **Originating call** → lands on `/calls?session=<uuid>` with that session selected and its transcript loaded.
5. A callback with `session_id: null` shows "Not linked to a session" — no dead anchor.
6. `Esc` and scrim click close the modal; focus returns to the triggering button (`modal.tsx` `restoreRef`).
7. Search for a word that exists only inside an `outcome_note` → the matching row is now inspectable instead of opaque.

### No design drift

8. `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/components/nexus/callback-lifecycle.tsx` → no hits.
9. `grep -n 'getDay(\|getHours(\|toLocaleString(' src/components/nexus/callback-lifecycle.tsx` → no hits.
10. Every class string traces to `decision-detail.tsx`, `customer-detail.tsx`, `callback-outcome.tsx` or `modal.tsx` (table in §4.4).
11. `git diff -- src/lib/nexus/status.ts` → empty.
12. `git diff -- src/lib/nexus/callback-view.ts src/lib/nexus/query-keys.ts src/lib/api/callbacks.server.ts` → empty.
13. `git diff --stat -- Frontend/admin_dashboard/package.json` → empty; no new dependency.
14. Overlay portals to `document.body` — inherited unmodified from `Modal`, so `PageSection`'s `.rise` transform cannot clip it.

### No backend core logic touched

15. `git diff --stat -- apps/ packages/ services/ infra/` → **empty**. No CORS change, no middleware change, no new route, no model change, no migration.
16. CORS/middleware additive-only: trivially satisfied, since neither was modified.

### Gates (operative set; `bun run build` is blocked by `ERR_REQUIRE_ESM` on Node v22)

17. `bunx tsc --noEmit` → exit 0.
18. Non-prettier lint findings still exactly **9** (7× `react-refresh/only-export-components`, 2× `react-hooks/exhaustive-deps`). The new file has a single export, so it adds none.
19. `bunx prettier --write src/components/nexus/callback-lifecycle.tsx src/routes/callbacks.tsx` — touched files only. **Never** `bun run format` (2704 findings repo-wide from the CRLF baseline).
20. No backend test run is required, because no backend file changed. `pytest apps/business-api/tests -q` should remain 24 passed if run for confidence.

---

## 6. Ambiguities needing your confirmation

1. **`MASTER_APPLY_RUNBOOK` §9 needs a correction.** It lists `attempts` / `outcome_note` / `completed_at` / `assigned_advisor_id` as backend-unexposed. They are exposed by `to_dict()`. Amend §9 as part of this change, or leave the runbook and keep the correction recorded only here?
2. **Should `Detail` be promoted to a full-row click?** `decisions.tsx` makes rows clickable; `/callbacks` uses hover buttons. Hover buttons were kept because a row-level click handler would fight the three nested buttons. Say the word if you want the two pages to converge.
3. **`attempts` will read 0 for dashboard-handled callbacks** because only `POST /api/v1/callbacks/claim` increments it, and no admin screen calls it. This is surfaced in a caption rather than hidden. If you want the number to be meaningful from this dashboard, exposing a "Claim" action on the pending queue is a **separate** cookbook — it is a write path, not a render gap. Confirm before it is planned.
4. **Lateness is deliberately not computed** (D15.3). If you want "honoured 4h 12m late", that needs a new coarse-interval formatter in `format.ts`, which is a new helper inside the locked design system. Needs your explicit go-ahead.

---

## 7. Files touched — summary

| File | Change | Lines |
| --- | --- | --- |
| `Frontend/admin_dashboard/src/components/nexus/callback-lifecycle.tsx` | **new** | ~145 |
| `Frontend/admin_dashboard/src/routes/callbacks.tsx` | modified: 1 import, 1 state hook, 1 cell replaced, 1 modal mounted | ~+20 / −11 |
| everything else | untouched | 0 |
