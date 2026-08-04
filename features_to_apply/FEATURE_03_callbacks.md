# Feature 3 — Callback Queue (Admin Dashboard)

**Cookbook for `Frontend/admin_dashboard/`. Target branch `version_80` (HEAD `eda5f58`).**

| | |
|---|---|
| Backend source of truth | `apps/business-api/src/business_api/callbacks.py` (`e3562a34`), `main.py` (`ff52daff`) |
| Models | `packages/persistence/src/persistence/models/conversation.py` (`ec4592ad`) — `CallbackSchedule`; `crm.py` (`65fe123c`) — `Customer` |
| Frontend surface | `src/routes/callbacks.tsx` (`d49d6009`) — pure mock, to be rewritten |
| New backend files | **zero** |
| New endpoints | **zero** |
| New npm dependencies | **zero** |
| New design tokens | **zero** |
| `routeTree.gen.ts` | **untouched** — `/callbacks` already exists |
| Builds on | Feature 0 (substrate), Feature 1 (`Modal`, `errorMessage` string branch), Feature 2 (business-timezone discipline) |

---

## 1. Feature name & scope

### 1.1 What this feature is

The callback queue is **the promise the platform makes when no advisor was free**. The voice agent
negotiates a slot with the caller, `reserve()` books it against real capacity, and a row lands in
`conversation.callback_schedules` with `status='pending'`.

The module docstring states the problem this feature closes, verbatim:

> Until now a callback was written with status='pending' and never read again - nobody could say
> whether it was ever made.

The admin dashboard is where a supervisor answers **"is the platform keeping its promises?"** — who is
waiting, who is late, how many attempts have already failed, and closing out the ones that are done.

### 1.2 In scope

- The queue table: pending / overdue / completed / cancelled / all, ordered exactly as the backend
  orders it (priority first, then time).
- Queue health counters: pending, overdue, completed.
- Search across customer name, phone, reason, preferred window and assigned advisor.
- Two lifecycle actions a supervisor legitimately owns:
  - **Record outcome** — reached (closes it) or no answer (returns it to the queue).
  - **Cancel** — the caller no longer needs it.
- Loading / empty / error states matching Features 1–2.

### 1.3 Deliberately out of scope — with reasons

These are decisions, not omissions. Each is justified from the code in §3.

| Excluded | Why |
|---|---|
| `POST /callbacks/claim` | It is a **queue pop**, not an assignment tool. It mutates state and inflates `attempts`. It belongs to an advisor workstation, not a supervision console. See F9. |
| Manual booking (`POST /callbacks/reserve`) | Cannot resolve a customer — there is no customer-search endpoint. Booking without `customer_id` creates an unactionable promise. See F11. |
| Reassigning a callback to a chosen advisor | **No endpoint exists.** Assignment happens only inside `reserve()` and `claim_next()`. Building it would be new business logic. See F9. |
| Slot browsing (`/callbacks/slots`, `/callbacks/check`) | These serve the agent's negotiation. With booking out of scope they have no admin consumer. |
| Opening the linked call session | `session_id` is exposed and `GET /api/v1/sessions/{id}` exists, but that is the Call-logs feature. See F13. |

---

## 2. Backend reference (exact names and paths)

### 2.1 Module constants — `business_api/callbacks.py`

```python
OPEN = "pending"
COMPLETED = "completed"
CANCELLED = "cancelled"

SLOT_MINUTES = int(os.getenv("CALLBACK_SLOT_MINUTES", "30"))
LEAD_MINUTES = int(os.getenv("CALLBACK_LEAD_MINUTES", "30"))
```

It imports `BUSINESS_TZ`, `DAY_END_HOUR`, `DAY_START_HOUR`, `ScheduleIndex`, `load_schedule` from
`business_api.availability` — the same module Feature 2 is built on. **The callback queue and the
coverage grid share one notion of who is working.** Everything Feature 2 established about
`is_on_call` and `Africa/Tunis` therefore applies here too.

### 2.2 The serializer — `to_dict(row, customer, advisor, now)`

This is the exact and complete shape of every callback the API returns. There are no other fields.

```python
{
  "id": str(row.id),
  "status": row.status,                       # 'pending' | 'completed' | 'cancelled'
  "scheduled_time": scheduled.isoformat(),    # UTC-aware ISO, or None
  "preferred_window": row.preferred_window,   # caller's own words, <=120 chars, nullable
  "reason": row.reason,                       # <=60 chars, nullable
  "priority_level": row.priority_level,       # int, default 1
  "attempts": row.attempts,                   # int, default 0
  "outcome_note": row.outcome_note,           # <=500 chars, nullable
  "completed_at": ...isoformat() or None,
  "overdue": bool(row.status == OPEN and scheduled and scheduled < now),
  "customer_id": str(...) or None,
  "customer_name": f"{customer.first_name} {customer.last_name}".strip() or None,
  "customer_phone": customer.contact_number or None,   # RAW, unmasked
  "assigned_advisor_id": str(...) or None,
  "assigned_advisor_name": advisor.full_name or None,
  "session_id": str(...) or None,
}
```

The comment on `preferred_window` is a product instruction and the UI must honour it:

> The caller's own words, kept verbatim: an advisor should see "demain matin", not just a
> timestamp the system guessed.

### 2.3 `CallbackSchedule` (DB truth)

`conversation.callback_schedules`, with `CheckConstraint("status IN ('pending','completed','cancelled')")`.

| Column | Type | Notes |
|---|---|---|
| `scheduled_time` | `DateTime(timezone=True)` NOT NULL | the slot instant |
| `priority_level` | `Integer` NOT NULL default `1` | **no check constraint — any integer is legal** |
| `status` | `String(20)` NOT NULL default `'pending'` | constrained to the 3 values |
| `assigned_advisor_id` | FK `routing.advisors.id` **`ondelete="SET NULL"`** | deleting an advisor orphans their callbacks rather than deleting them |
| `preferred_window` | `String(120)` | |
| `reason` | `String(60)` | |
| `attempts` | `Integer` NOT NULL default `0` | |
| `outcome_note` | `String(500)` | |
| `completed_at` | `DateTime(timezone=True)` | |

`Customer.contact_number` is `String(20)`, nullable. `Customer` has `first_name`/`last_name` both
NOT NULL, so `customer_name` is non-empty whenever a customer is attached.

### 2.4 Repository functions used by this feature

| Function | Behaviour that matters |
|---|---|
| `list_callbacks(session, status=OPEN, overdue_only=False, limit=100)` | `ORDER BY priority_level DESC, scheduled_time ASC`, `LIMIT limit`. `if status:` — **a falsy status skips the filter entirely**. `overdue_only` adds `scheduled_time < now(UTC)`. |
| `queue_stats(session)` | Three unbounded `COUNT(*)`: pending, overdue (pending AND past), completed. |
| `complete_callback(session, callback_id, note="", reached=True)` | `reached=True` → `status=COMPLETED`, `completed_at=now`. `reached=False` → **status unchanged**, `assigned_advisor_id=None`. Note is `(note or "")[:500] or row.outcome_note`. Returns `None` if not found. |
| `cancel_callback(session, callback_id, note="")` | `status=CANCELLED`, same note rule. Returns `None` if not found. |
| `claim_next(session, advisor_id=None)` | Pops the next row `FOR UPDATE SKIP LOCKED`, assigns if unassigned, **`row.attempts += 1`**. Not used by this feature. |

### 2.5 The `_hydrate` helper

Every list result passes through `_hydrate`, which batches two `IN` queries (customers, advisors) and
stamps a single shared `now`. Consequence: **`overdue` is evaluated against one server clock for the
whole page**, which is why the client must never recompute it (F2).

---

## 3. Findings that shape the design

Eleven behaviours in this code contradict what a reasonable implementation would assume. Each one
below is derived from the source, and each drives a concrete decision.

### F1. An empty `status` returns **every** status — this is how "All" is built

```python
def list_callbacks(session, status: str = OPEN, overdue_only: bool = False, limit: int = 100):
    stmt = select(CallbackSchedule).order_by(...).limit(limit)
    if status:
        stmt = stmt.where(CallbackSchedule.status == status)
```

`status` is typed `str = "pending"`, so `?status=` binds the **empty string**, which is falsy, which
skips the `WHERE`. There is no `status=all` sentinel and no list parameter.

**Decision.** The "All" scope sends `status: ""`. This is the only way to get a mixed list, and it
costs nothing. It must be sent as an explicit empty string — omitting the parameter falls back to the
`"pending"` default and would silently show the wrong scope.

### F2. `overdue` is server-computed; never recompute it

`overdue` is `status == 'pending' AND scheduled_time < now`, evaluated with the API's clock inside
`_hydrate`. A browser comparison would drift with clock skew, and — more importantly — would have to
choose a timezone, reintroducing the Feature 2 bug class.

**Decision.** Render the boolean. `callback-view.ts` contains no date comparison of any kind.

### F3. There is **no** `local` string here — this feature must convert, and Feature 2's rule inverts

This is the single easiest way to get this feature wrong.

`coverage_report()` returns both `at` (UTC) and `local` (business-local wall clock), which is why
Feature 2's binding rule was *render `local` verbatim, never `new Date(at)`*.

`to_dict()` for a callback returns **only** `scheduled_time.isoformat()` — a UTC-aware instant. There
is no pre-formatted local string anywhere in the callback payload.

So Feature 3 **must** convert. And it must convert into **`BUSINESS_TZ`**, not the browser's zone: the
slot grid, `DAY_START_HOUR`/`DAY_END_HOUR`, and everything Feature 2 renders are business-local. An
admin working from Paris in July who sees browser-local times would read `10:00` for a slot the
advisor will work at `09:00`, and it would disagree with the coverage grid on the very next page.

**Decision.** One helper, `formatBusinessTime(iso, timeZone)`, built on `Intl.DateTimeFormat` with an
explicit `timeZone`. No bare `toLocaleString()`, no `getHours()`, no `getDay()` anywhere in the
feature. Same grep gate as Feature 2.

### F3b. Where the business timezone comes from

The callback endpoints never state their timezone. The only endpoint that exposes it is
`GET /api/v1/advisors/coverage`, which returns `"timezone"` — and Feature 2 already consumes it.

Three options were considered:

1. **Hard-code `"Africa/Tunis"`** — rejected. It is `os.getenv("CALLBACK_TIMEZONE", ...)`; hard-coding
   creates silent drift the day someone changes it, which is exactly the class of bug F3 is about.
2. **Read a frontend env var** — rejected. Two sources of truth for one value, and nothing keeps them
   equal.
3. **Reuse `getCoverage({ days: 1 })`** — chosen. It is the backend's own answer, it is already wired
   and typed from Feature 2, TanStack Query dedupes and caches it, and the same response carries
   `advisors_total`, which the page uses for the rota caption.

**Decision.** The page issues `getCoverage({ days: 1 })` alongside the queue query, purely to obtain
`timezone`. Cost is one small request (ten rows at most). A dedicated `GET /api/v1/config` endpoint
would be cleaner and is permitted by the "expose existing data" rule — **flagged in §8.1** rather than
built, because it is not needed to ship this feature.

> If `getCoverage` fails while the queue query succeeds, the page renders times with the fallback
> `"UTC"` **and** shows an inline caption saying the business timezone could not be loaded. It never
> silently renders in a guessed zone.

### F4. The list is **priority-ordered first**, not chronological

```python
.order_by(CallbackSchedule.priority_level.desc(), CallbackSchedule.scheduled_time.asc())
```

A table that shows only times will look randomly sorted the moment one row has `priority_level=2`.

**Decision.** Priority is a visible column, and the client **never re-sorts**. The row order is the
backend's answer, and the toolbar says so.

### F4b. `priority_level` is an unconstrained integer

The model has no check constraint and no enum: `priority_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))`.
`reserve()` defaults `priority: int = 1`. Nothing in the codebase defines what `2` or `7` means.

The design system has a `PriorityMeter({ priority })` primitive whose `LEVEL_TONE` table is keyed by
`critical | high | medium | low | inert` — **string levels, not integers**.

**Decision.** Do **not** use `PriorityMeter`. Mapping an unbounded integer onto five named severity
levels means inventing thresholds the backend does not define, and the whole point of this phase is
not to invent backend semantics. Priority renders as an existing `Token` showing `P{n}`, and only when
`priority_level !== 1` — so the default queue stays visually calm and any genuinely elevated row is
obvious. If you later define the integer scale, swapping in `PriorityMeter` is a one-line change;
**flagged in §8.2**.

### F5. Two of the three statuses do not exist in `status.ts`

`status.ts` is the canonical truth table and its header is explicit: *"No status exists outside it."*
It contains `pending`, `resolved`, `closed`, `overdue` — but **no `completed` and no `cancelled`**.

And from Feature 1's audit, `StatusChip` begins:

```tsx
const def = STATUS[status];
if (!def) return null;
```

Passing `"completed"` straight through renders **nothing at all** — a blank cell, silently. This is
precisely the defect class Feature 1 guarded against with `advisorStatusKey`.

**Decision.** A total mapping function, mirroring `advisorStatusKey`:

| Backend state | Chip key | Reads as |
|---|---|---|
| `pending` **and** `overdue: true` | `overdue` | Overdue (triangle, critical, inverted) |
| `pending` | `pending` | Pending (ring, medium, outline) |
| `completed` | `resolved` | Resolved (disc, low, soft) |
| `cancelled` | `closed` | Closed (square, inert, flat) |
| anything else | `closed` | never blank |

The `overdue` row is the payoff: the truth table already has an `overdue` entry with exactly the right
tone, so lateness is legible at a glance without adding a token, a colour, or a column.

`status.ts` is **not modified**.

### F6. `reached: false` does not complete anything — and does not count an attempt

```python
if reached:
    row.status = COMPLETED
    row.completed_at = datetime.now(UTC)
else:
    row.assigned_advisor_id = None  # back to the queue for another attempt
```

With `reached=False` the status stays `pending`, the row returns to the queue **unassigned**, and
`attempts` is *not* touched — only `claim_next()` increments it. The docstring is explicit: *"a caller
who did not pick up has not been helped"*.

**Decision.** The outcome modal offers two clearly different actions with honest labels —
**"Reached — close callback"** and **"No answer — return to queue"** — and the second explains, in the
modal, that the callback stays in the queue and loses its assigned advisor. Labelling that button
"Complete" would be a lie about what the row does next.

### F7. An empty note cannot clear an existing note

```python
row.outcome_note = (note or "")[:500] or row.outcome_note
```

An empty string falls through to the right-hand side and the **previous** note survives. Truncation
is silent at 500.

**Decision.** The note field is `maxLength={500}` with a live counter past 450, and the modal states
that leaving it blank keeps any existing note. No attempt is made to clear a note — the API cannot.

### F8. `complete` and `cancel` require a body; omitting it is a 422

`CallbackOutcome` is a required Pydantic body parameter on both routes. Its fields are
`note: str = ""`, `reached: bool = True`, `advisor_id: str | None = None`. `cancel_callback()` ignores
everything except `note`.

**Decision.** Always send an explicit object. `cancelCallback` sends `{ note }` only — sending
`reached` to an endpoint that discards it would imply a behaviour that does not exist.

### F9. There is no way to assign a callback to a chosen advisor

Assignment happens in exactly two places: `_pick_advisor()` inside `reserve()` (least-loaded advisor
actually working at that instant), and `claim_next()` (pops the next row for whoever is asking). There
is no `PATCH /callbacks/{id}` and no assignment endpoint of any kind.

`claim_next()` additionally increments `attempts` and mutates assignment — a supervisor clicking a
"claim" button in a dashboard would quietly take a caller off the queue and inflate that caller's
failure count.

**Decision.** No claim button, no reassign control, no advisor dropdown. The advisor column is
**read-only**. Reassignment is real missing business logic; per the phase rule it is **flagged in
§8.3**, not built.

### F10. All four booking refusals collapse into one opaque 409

`reserve()` returns `None` — surfaced as `409 "slot no longer available"` — for four distinct causes:
off-grid minute, `capacity <= 0` (nobody works then), slot full, and no advisor free at that instant.
`check_slot()` by contrast returns a machine-readable `reason` (`unparsable | too_soon | closed |
full | ok`) plus real alternatives.

This is recorded because it is the reason booking is out of scope: any admin booking UI would need
to pre-flight through `/check` to say anything truthful. Noted for whoever revisits §8.4.

### F11. Booking cannot identify a customer

`CallbackReservation` accepts `customer_id` as an optional opaque UUID. There is **no customer search
endpoint** — only `GET /api/v1/customers/{customer_id}/360`, which requires an id you already have.
An admin cannot go from "Mrs Ben Salah, 216…" to a UUID.

A booking made without `customer_id` produces a row whose `customer_name` and `customer_phone` are
both `null`: an advisor receives a slot with nobody to call.

**Decision.** Manual booking is out of scope, and the reason is a **missing backend capability**, not
a UI shortcut. **Flagged in §8.4.**

### F12. `customer_phone` is returned raw and unmasked

`to_dict` returns `customer.contact_number` verbatim. The existing template already established the
house rule — `callbacks.tsx` renders `maskPhone(c.phone)`, and Feature 1 kept `maskPhone` in the
advisors table.

**Decision.** Render `maskPhone(customer_phone)`. The masking is presentational only; the API response
still contains the full number, which is stated here so nobody mistakes this for a privacy control.

### F13. `session_id` is the bridge to the call record — but not yet

Every callback may carry `session_id`, and `GET /api/v1/sessions/{session_id}` (conseiller) returns the
masked transcript and sentiment timeline. That is the Call-logs feature.

**Decision.** Not wired. Recorded in §8.5 so the Call-logs cookbook picks the thread up.

### F14. `stats` and the list disagree by design — the table can silently truncate

`queue_stats()` counts without a limit. `list_callbacks()` caps at `limit` (default 100) with **no
offset parameter**, so there is no pagination available at all.

With 140 pending callbacks the header reads "140 pending" and the table shows 100 rows, with nothing
indicating the other 40 exist.

**Decision.** The footer compares `rows.length` against the scope's authoritative count and, when the
list is capped, says so explicitly: *"Showing the first 100 of 140 · raise the limit to see more."*
A limit control (100 / 250 / 500) is provided, since `limit` is unclamped server-side. Real pagination
needs an `offset` parameter — **flagged in §8.6**.

### F15. `overdue_only` is orthogonal to `status`, which makes some combinations lie

`overdue_only` appends `scheduled_time < now` regardless of status, while the `overdue` **field** is
true only for pending rows. So `status=completed&overdue_only=true` returns completed callbacks that
were scheduled in the past — every one of them displaying `overdue: false`.

**Decision.** Overdue is modelled as a **scope**, not as an independent toggle. The five scopes emit
only meaningful combinations, and the contradictory pairing is unreachable from the UI.

---

## 4. Endpoint contracts (verified against `main.py`)

The role column is the **exact** decorator in `main.py`. `require_role(minimum)` is a factory
performing a **minimum-rank** check against `_ROLE_RANK = {conseiller: 1, superviseur: 2,
administrateur: 3}`, so an `administrateur` session satisfies all of them. Mirror the exact contract
role anyway, as Feature 2 §4.1 established.

### 4.1 Reused — nothing new

| Method | Path | Role | Query / body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/callbacks` | `conseiller` | `status` (str, default `"pending"`, **empty = all**), `overdue_only` (bool), `limit` (int, default 100) | `{ "callbacks": Callback[] }` |
| `GET` | `/api/v1/callbacks/stats` | `superviseur` | — | `{ "pending": int, "overdue": int, "completed": int }` |
| `POST` | `/api/v1/callbacks/{callback_id}/complete` | `conseiller` | body `{ note, reached, advisor_id? }` | the updated callback; `404 "callback not found"` |
| `POST` | `/api/v1/callbacks/{callback_id}/cancel` | `superviseur` | body `{ note, reached, advisor_id? }` (only `note` is read) | the updated callback; `404 "callback not found"` |
| `GET` | `/api/v1/advisors/coverage` | `superviseur` | `days=1` | used only for `timezone` + `advisors_total` (F3b) |

### 4.2 New endpoints

**None.** No backend file is created or modified. No CORS or middleware change — everything continues
to flow through the TanStack server proxy established in Feature 0, so the browser never contacts
`:8108` directly.

---

## 5. Files

### 5.1 Added

| File | Role |
|---|---|
| `src/lib/api/callbacks.server.ts` | 4 server functions + zod validation |
| `src/lib/nexus/callback-view.ts` | pure helpers: status mapping, business-time formatting, search, labels |
| `src/components/nexus/callback-outcome.tsx` | outcome + cancel modals |

### 5.2 Modified

| File | Change |
|---|---|
| `src/routes/callbacks.tsx` | **rewritten** — mock replaced by live queue |
| `src/lib/nexus/query-keys.ts` | append `callbackKeys` |
| `src/lib/nexus/data.ts` | remove the `CALLBACKS` mock export (and its row type) |

### 5.3 Explicitly untouched

`status.ts`, `primitives.tsx`, `modal.tsx`, `blocks.tsx`, `format.ts`, `nav.ts`, `routeTree.gen.ts`,
`app-sidebar.tsx`, `app-topbar.tsx`, `styles.css`, and every backend file.

> `/callbacks` already exists in `nav.ts` (section `OPERATIONS`) and in `routeTree.gen.ts`. Unlike
> Feature 2, this feature adds **no route and no nav entry**, so `routeTree.gen.ts` must show an empty
> diff. If it changes, something regenerated wrongly — revert it.

---

## 6. Implementation

### 6.1 `src/lib/api/callbacks.server.ts` — new

> **Copy the middleware composition verbatim from `src/lib/api/availability.server.ts`.** That file is
> the proven shape on this codebase (Feature 2, applied and E2E-verified). The composition below
> matches it; if the applied file differs in any detail, the applied file wins.

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

import { businessApi } from "./business-api";
import { authedMiddleware, requireRole } from "./middleware";

/**
 * The callback queue.
 *
 * Contract notes that are easy to get wrong and are enforced here:
 *  - `status: ""` is the ONLY way to list every status (business_api/callbacks.py:list_callbacks
 *    guards the filter with `if status:`). It must be sent explicitly; omitting it defaults to
 *    "pending" server-side.
 *  - `overdue_only` is orthogonal to `status`, so only the combinations produced by the UI's five
 *    scopes are ever emitted.
 *  - complete/cancel take a REQUIRED body. Omitting it is a 422.
 */

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

export type CallbackStats = {
  pending: number;
  overdue: number;
  completed: number;
};

// "" is meaningful (all statuses) — do not coerce it away.
const ListInput = z.object({
  status: z.enum(["pending", "completed", "cancelled", ""]),
  overdueOnly: z.boolean(),
  limit: z.number().int().min(1).max(1000),
});

const OutcomeInput = z.object({
  callbackId: z.string().min(1),
  note: z.string().max(500),
  reached: z.boolean(),
});

const CancelInput = z.object({
  callbackId: z.string().min(1),
  note: z.string().max(500),
});

export const listCallbacks = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    const result = await businessApi<{ callbacks: Callback[] }>("/api/v1/callbacks", {
      method: "GET",
      query: {
        status: data.status,
        overdue_only: data.overdueOnly,
        limit: data.limit,
      },
      role: context.session.role,
    });
    return result.callbacks ?? [];
  });

export const getCallbackStats = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) =>
    businessApi<CallbackStats>("/api/v1/callbacks/stats", {
      method: "GET",
      role: context.session.role,
    }),
  );

/**
 * reached=true  -> status becomes 'completed', completed_at is stamped.
 * reached=false -> status stays 'pending', assigned_advisor_id is cleared, attempts is NOT
 *                  incremented (only claim_next does that).
 * An empty note leaves any existing note in place; it cannot be cleared.
 */
export const completeCallback = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => OutcomeInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Callback>(`/api/v1/callbacks/${data.callbackId}/complete`, {
      method: "POST",
      body: { note: data.note, reached: data.reached },
      role: context.session.role,
    }),
  );

/** cancel_callback reads only `note`; `reached` is deliberately not sent. */
export const cancelCallback = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => CancelInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Callback>(`/api/v1/callbacks/${data.callbackId}/cancel`, {
      method: "POST",
      body: { note: data.note },
      role: context.session.role,
    }),
  );
```

> **`query` and booleans.** `businessApi` serialises query values; `overdue_only: false` must reach
> FastAPI as `false`, and `status: ""` must be emitted as an empty value rather than dropped. Confirm
> against the Feature 0 implementation of `businessApi`; if it strips empty strings or falsy values,
> send `status` through as a string and build the query with `String(value)` there. **This is the one
> integration detail to verify first** — F1 depends on it entirely.

### 6.2 `src/lib/nexus/callback-view.ts` — new

```ts
import { maskPhone } from "./format";
import type { Callback } from "@/lib/api/callbacks.server";

/** The five scopes. Each maps to one legal (status, overdue_only) pair — see F15. */
export type CallbackScope = "pending" | "overdue" | "completed" | "cancelled" | "all";

export const CALLBACK_SCOPES: Array<{ id: CallbackScope; label: string }> = [
  { id: "pending", label: "Pending" },
  { id: "overdue", label: "Overdue" },
  { id: "completed", label: "Completed" },
  { id: "cancelled", label: "Cancelled" },
  { id: "all", label: "All" },
];

export function scopeQuery(scope: CallbackScope): {
  status: "pending" | "completed" | "cancelled" | "";
  overdueOnly: boolean;
} {
  switch (scope) {
    case "pending":
      return { status: "pending", overdueOnly: false };
    case "overdue":
      return { status: "pending", overdueOnly: true };
    case "completed":
      return { status: "completed", overdueOnly: false };
    case "cancelled":
      return { status: "cancelled", overdueOnly: false };
    case "all":
    default:
      // Empty string == no WHERE clause server-side. Not a bug; the only way to list everything.
      return { status: "", overdueOnly: false };
  }
}

/**
 * Total mapping onto status.ts keys. StatusChip returns null for unknown keys, so an unmapped
 * value would render a blank cell (the Feature 1 defect). 'completed' and 'cancelled' do not
 * exist in the truth table; 'overdue' does, and carries exactly the right tone.
 */
export function callbackStatusKey(row: Pick<Callback, "status" | "overdue">): string {
  if (row.status === "pending") return row.overdue ? "overdue" : "pending";
  if (row.status === "completed") return "resolved";
  if (row.status === "cancelled") return "closed";
  return "closed";
}

/**
 * Format a UTC instant in the BUSINESS timezone.
 *
 * Callbacks carry no pre-formatted local string (unlike coverage_report), so conversion is
 * mandatory here — and it must target the business zone, not the browser's, or this page will
 * disagree with /availability. hourCycle h23 avoids the "24:00" that hour12:false can emit.
 * No getDay(), no getHours(), no toLocaleString().
 */
export function formatBusinessTime(iso: string | null, timeZone: string): string {
  if (!iso) return "\u2014";
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return "\u2014";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = `${get("weekday")} ${get("day")} ${get("month")}`.trim();
  const time = `${get("hour")}:${get("minute")}`;
  return day ? `${day} \u00b7 ${time}` : time;
}

/** Short form for dense cells: "03 Aug 09:00". */
export function formatBusinessDayTime(iso: string | null, timeZone: string): string {
  if (!iso) return "\u2014";
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return "\u2014";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")} ${get("month")} ${get("hour")}:${get("minute")}`;
}

export function callbackCustomer(row: Callback): { name: string; phone: string } {
  return {
    name: row.customer_name?.trim() || "Unknown caller",
    phone: row.customer_phone ? maskPhone(row.customer_phone) : "\u2014",
  };
}

/** priority_level is an unconstrained integer with no defined scale — show it, don't grade it. */
export function priorityLabel(level: number): string | null {
  if (!Number.isFinite(level) || level === 1) return null;
  return `P${level}`;
}

export function callbackMatches(row: Callback, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    row.customer_name,
    row.customer_phone,
    row.assigned_advisor_name,
    row.preferred_window,
    row.reason,
    row.outcome_note,
  ];
  return haystack.some((v) => (v ?? "").toLowerCase().includes(q));
}

/** The count the footer compares against, so truncation is visible (F14). */
export function scopeTotal(
  scope: CallbackScope,
  stats: { pending: number; overdue: number; completed: number } | undefined,
): number | null {
  if (!stats) return null;
  if (scope === "pending") return stats.pending;
  if (scope === "overdue") return stats.overdue;
  if (scope === "completed") return stats.completed;
  return null; // queue_stats does not count cancelled, and 'all' has no single counter
}
```

> `scopeTotal` returns `null` for `cancelled` and `all` because **`queue_stats` genuinely does not
> count them**. Inventing a total there would be fabricating data; the footer simply omits the
> comparison for those scopes and still warns when `rows.length === limit`.

### 6.3 `src/lib/nexus/query-keys.ts` — modified

Append a standalone export, exactly as Feature 2 appended `availabilityKeys`:

```ts
export const callbackKeys = {
  all: ["callbacks"] as const,
  list: (status: string, overdueOnly: boolean, limit: number) =>
    ["callbacks", "list", status, overdueOnly, limit] as const,
  stats: () => ["callbacks", "stats"] as const,
};
```

Mutations invalidate `callbackKeys.all` **and** `callbackKeys.stats()`; completing a callback changes
both the rows and the counters.

### 6.4 `src/components/nexus/callback-outcome.tsx` — new

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Modal } from "./modal";
import { Button, Token } from "./primitives";
import { InlineError } from "./states";
import { callbackKeys } from "@/lib/nexus/query-keys";
import { formatBusinessTime } from "@/lib/nexus/callback-view";
import { cancelCallback, completeCallback, type Callback } from "@/lib/api/callbacks.server";

type Props = {
  callback: Callback;
  timeZone: string;
  onClose: () => void;
};

/**
 * Record the outcome of an attempted callback.
 *
 * Two outcomes, deliberately worded differently, because the backend does two different things:
 *   reached=true  -> closed
 *   reached=false -> stays pending, returns to the queue unassigned
 */
export function CallbackOutcomeModal({ callback, timeZone, onClose }: Props) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: (reached: boolean) =>
      completeCallback({ data: { callbackId: callback.id, note, reached } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: callbackKeys.all });
      onClose();
    },
  });

  return (
    <Modal
      title="Record outcome"
      subtitle={`${callback.customer_name ?? "Unknown caller"} \u00b7 ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
      onClose={onClose}
      footer={
        <div className="flex items-center justify-between gap-sp-5">
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Close
          </Button>
          <div className="flex items-center gap-sp-4">
            <Button
              variant="secondary"
              onClick={() => mutation.mutate(false)}
              disabled={mutation.isPending}
            >
              No answer \u2014 return to queue
            </Button>
            <Button
              variant="primary"
              onClick={() => mutation.mutate(true)}
              disabled={mutation.isPending}
            >
              Reached \u2014 close callback
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-sp-6">
        {callback.attempts > 0 ? (
          <div className="flex items-center gap-sp-3">
            <Token>{callback.attempts} attempt{callback.attempts === 1 ? "" : "s"}</Token>
            <span className="t-caption text-ink-4">already recorded on this callback.</span>
          </div>
        ) : null}

        <label className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Outcome note</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value.slice(0, 500))}
            maxLength={500}
            rows={4}
            className="w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            placeholder="What happened on this call?"
          />
          <span className="t-caption text-ink-5">
            {note.length > 450 ? `${500 - note.length} characters left. ` : ""}
            Leaving this blank keeps any note already on the callback.
          </span>
        </label>

        <p className="t-caption text-ink-4">
          \u201cNo answer\u201d keeps the callback pending and releases the assigned advisor, so it
          returns to the queue for another attempt.
        </p>

        {mutation.isError ? <InlineError error={mutation.error} /> : null}
      </div>
    </Modal>
  );
}

/** Cancelling is terminal and is a supervisor action (superviseur on the route). */
export function CallbackCancelModal({ callback, timeZone, onClose }: Props) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () => cancelCallback({ data: { callbackId: callback.id, note } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: callbackKeys.all });
      onClose();
    },
  });

  return (
    <Modal
      title="Cancel callback"
      subtitle={`${callback.customer_name ?? "Unknown caller"} \u00b7 ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
      onClose={onClose}
      footer={
        <div className="flex items-center justify-between gap-sp-5">
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Keep it
          </Button>
          <Button
            variant="primary"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            Cancel callback
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-sp-6">
        <p className="t-body text-ink-2">
          This closes the promise made to the caller. It cannot be undone \u2014 there is no way to
          move a cancelled callback back to pending.
        </p>
        <label className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Reason (optional)</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value.slice(0, 500))}
            maxLength={500}
            rows={3}
            className="w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            placeholder="Why is this callback no longer needed?"
          />
        </label>
        {mutation.isError ? <InlineError error={mutation.error} /> : null}
      </div>
    </Modal>
  );
}
```

> **Match `Modal`'s real prop names.** The signature above (`title`, `subtitle`, `onClose`, `footer`,
> children) is the shape Features 1–2 use. Open `src/components/nexus/modal.tsx` and align exactly; it
> already portals to `document.body`, so no containing-block work is needed here.
>
> **`InlineError`.** Feature 1 fixed `errorMessage()` to pass plain strings through, and Feature 2
> confirmed the `error={...}` call site. Use the same prop shape as `advisor-form.tsx`.
>
> The `\u2014` / `\u00b7` / `\u201c` escapes above are written literally in this document to keep it
> copy-safe; in the real source, type the characters directly (— · “ ”).

### 6.5 `src/routes/callbacks.tsx` — rewritten

```tsx
import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PhoneOff } from "lucide-react";

import { PageSection } from "@/components/nexus/app-topbar";
import {
  Avatar,
  Button,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import {
  CallbackCancelModal,
  CallbackOutcomeModal,
} from "@/components/nexus/callback-outcome";
import { getCoverage } from "@/lib/api/availability.server";
import { getCallbackStats, listCallbacks, type Callback } from "@/lib/api/callbacks.server";
import { callbackKeys, availabilityKeys } from "@/lib/nexus/query-keys";
import {
  CALLBACK_SCOPES,
  callbackCustomer,
  callbackMatches,
  callbackStatusKey,
  formatBusinessDayTime,
  priorityLabel,
  scopeQuery,
  scopeTotal,
  type CallbackScope,
} from "@/lib/nexus/callback-view";
import { initials } from "@/lib/nexus/format";

const LIMITS = [
  { id: "100", label: "100" },
  { id: "250", label: "250" },
  { id: "500", label: "500" },
];

export const Route = createFileRoute("/callbacks")({
  component: CallbacksPage,
  head: () => ({ meta: [{ title: "Callbacks \u2014 Nexus" }] }),
});

function CallbacksPage() {
  const [scope, setScope] = useState<CallbackScope>("pending");
  const [limit, setLimit] = useState(100);
  const [query, setQuery] = useState("");
  const [outcomeFor, setOutcomeFor] = useState<Callback | null>(null);
  const [cancelFor, setCancelFor] = useState<Callback | null>(null);

  const { status, overdueOnly } = scopeQuery(scope);

  const listQuery = useQuery({
    queryKey: callbackKeys.list(status, overdueOnly, limit),
    queryFn: () => listCallbacks({ data: { status, overdueOnly, limit } }),
  });

  const statsQuery = useQuery({
    queryKey: callbackKeys.stats(),
    queryFn: () => getCallbackStats(),
  });

  // Callbacks carry no business-local string, and the queue endpoints never state their zone.
  // coverage_report is the backend's own answer for CALLBACK_TIMEZONE (see F3b).
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });

  const timeZone = coverageQuery.data?.timezone ?? "UTC";
  const zoneKnown = Boolean(coverageQuery.data?.timezone);

  const rows = listQuery.data ?? [];
  const visible = useMemo(
    () => rows.filter((row) => callbackMatches(row, query)),
    [rows, query],
  );

  const total = scopeTotal(scope, statsQuery.data);
  const truncated = rows.length >= limit;

  return (
    <PageSection>
      <div className="mb-sp-6 flex flex-wrap items-baseline gap-sp-5">
        <span className="t-caption text-ink-4">
          {statsQuery.data
            ? `${statsQuery.data.pending} pending \u00b7 ${statsQuery.data.overdue} overdue \u00b7 ${statsQuery.data.completed} completed`
            : "Queue health loading\u2026"}
        </span>
        <span className="t-caption text-ink-5">
          {zoneKnown
            ? `times in ${timeZone}`
            : "business timezone unavailable \u2014 times shown in UTC"}
        </span>
      </div>

      <TableShell
        toolbar={
          <div className="flex w-full items-center justify-between gap-sp-5">
            <div className="flex items-center gap-sp-5">
              <Segmented
                items={CALLBACK_SCOPES}
                active={scope}
                onSelect={(id) => setScope(id as CallbackScope)}
              />
              <div className="w-[260px]">
                <SearchInput
                  placeholder="Search caller, advisor, reason\u2026"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            </div>
            <Segmented
              items={LIMITS}
              active={String(limit)}
              onSelect={(id) => setLimit(Number(id))}
            />
          </div>
        }
        head={
          <tr>
            <Th>Caller</Th>
            <Th>Scheduled</Th>
            <Th>Window</Th>
            <Th>Reason</Th>
            <Th>Advisor</Th>
            <Th>Attempts</Th>
            <Th>Status</Th>
            <Th> </Th>
          </tr>
        }
        footer={
          <>
            <span className="t-caption text-ink-4">
              {visible.length === rows.length
                ? `${rows.length} callback${rows.length === 1 ? "" : "s"}`
                : `${visible.length} of ${rows.length} callbacks`}
            </span>
            <span className="t-caption text-ink-5">
              {truncated
                ? total !== null
                  ? `Showing the first ${limit} of ${total} \u00b7 raise the limit to see more`
                  : `Showing the first ${limit} \u00b7 raise the limit to see more`
                : "Ordered by priority, then soonest first"}
            </span>
          </>
        }
      >
        {listQuery.isPending ? (
          <TableSkeleton rows={6} cols={8} />
        ) : listQuery.isError ? (
          <TableErrorRow
            colSpan={8}
            message="Could not load the callback queue"
            onRetry={() => listQuery.refetch()}
          />
        ) : visible.length === 0 ? (
          <tr>
            <Td colSpan={8}>
              <EmptyState
                icon={PhoneOff}
                title={query ? "No matching callbacks" : "Nothing in this queue"}
                description={
                  query
                    ? "No callback matches that search in the current scope."
                    : "When the agent cannot reach an advisor it books a callback here."
                }
              />
            </Td>
          </tr>
        ) : (
          visible.map((row) => {
            const customer = callbackCustomer(row);
            const priority = priorityLabel(row.priority_level);
            return (
              <tr key={row.id} className="group">
                <Td>
                  <div className="flex flex-col">
                    <span className="t-ui text-ink-1">{customer.name}</span>
                    <span className="t-mono-s text-ink-4">{customer.phone}</span>
                  </div>
                </Td>
                <Td>
                  <div className="flex items-center gap-sp-3">
                    <span className="t-mono-s text-ink-2">
                      {formatBusinessDayTime(row.scheduled_time, timeZone)}
                    </span>
                    {priority ? <Token strong>{priority}</Token> : null}
                  </div>
                </Td>
                <Td>
                  {row.preferred_window ? (
                    <Token>{row.preferred_window}</Token>
                  ) : (
                    <span className="t-caption text-ink-5">\u2014</span>
                  )}
                </Td>
                <Td>
                  <span className="t-ui-regular text-ink-3">{row.reason ?? "\u2014"}</span>
                </Td>
                <Td>
                  {row.assigned_advisor_name ? (
                    <div className="flex items-center gap-sp-4">
                      <Avatar size="sm" initials={initials(row.assigned_advisor_name)} />
                      <span className="t-ui text-ink-2">{row.assigned_advisor_name}</span>
                    </div>
                  ) : (
                    <span className="t-caption text-ink-5">Unassigned</span>
                  )}
                </Td>
                <Td>
                  {row.attempts > 0 ? (
                    <Token strong={row.attempts > 1}>{row.attempts}</Token>
                  ) : (
                    <span className="t-caption text-ink-5">\u2014</span>
                  )}
                </Td>
                <Td>
                  <StatusChip status={callbackStatusKey(row)} />
                </Td>
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
              </tr>
            );
          })
        )}
      </TableShell>

      {outcomeFor ? (
        <CallbackOutcomeModal
          callback={outcomeFor}
          timeZone={timeZone}
          onClose={() => setOutcomeFor(null)}
        />
      ) : null}
      {cancelFor ? (
        <CallbackCancelModal
          callback={cancelFor}
          timeZone={timeZone}
          onClose={() => setCancelFor(null)}
        />
      ) : null}
    </PageSection>
  );
}
```

**Call-site notes**

- `SearchInput` was uncontrolled in the template; Feature 1 already made it controlled for
  `/advisors`. Reuse whatever shape `advisors.tsx` now uses — do not change the primitive again.
- `Segmented` is safe inside forms since the Feature 1 `type="button"` fix. It is used twice here.
- `EmptyState`'s `icon` prop: pass it exactly the way `advisors.tsx` does (component reference vs.
  element). Mirror, do not guess.
- The actions cell mirrors the Feature 1 hover pattern, including `focus-within:opacity-100` so the
  controls are keyboard-reachable.

### 6.6 `src/lib/nexus/data.ts` — modified

Remove the `CALLBACKS` export and its row type, exactly as Feature 1 removed `ADVISORS`. Confirm no
other module imports it:

```bash
rg -n "CALLBACKS" Frontend/admin_dashboard/src
```

Only `routes/callbacks.tsx` referenced it, and that file is rewritten.

---

## 7. Validation checklist

### 7.1 Static

- [ ] `bun --bun tsc --noEmit` → exit 0.
- [ ] `bun --bun run lint` → the known baseline of 36 problems, **no new ones**.
- [ ] `bun --bun run build` → exit 0.
- [ ] `git diff --stat` shows **zero** files under `apps/`, `packages/`, `services/`.
- [ ] `package.json` and `bun.lock` unchanged.
- [ ] **`routeTree.gen.ts` diff is empty** (no route added).
- [ ] `status.ts`, `primitives.tsx`, `modal.tsx`, `blocks.tsx`, `nav.ts` unchanged.
- [ ] Grep the three new files for `#`, `rgb(`, and Tailwind palette classes → no hits.
- [ ] Grep the three new files for `getDay(`, `getHours(`, `toLocaleString(`, `toLocaleTimeString(`
      → **no hits**. Only `Intl.DateTimeFormat` with an explicit `timeZone`.

### 7.2 Pure helpers (no browser needed)

- [ ] `scopeQuery("all")` → `{ status: "", overdueOnly: false }`.
- [ ] `scopeQuery("overdue")` → `{ status: "pending", overdueOnly: true }`.
- [ ] `callbackStatusKey({status:"pending", overdue:true})` → `"overdue"`.
- [ ] `callbackStatusKey({status:"completed", overdue:false})` → `"resolved"`.
- [ ] `callbackStatusKey({status:"cancelled", overdue:false})` → `"closed"`.
- [ ] `callbackStatusKey({status:"weird", overdue:false})` → `"closed"` (never blank).
- [ ] `formatBusinessTime("2026-08-03T08:00:00+00:00", "Africa/Tunis")` → `09:00`, **and the same
      string when the OS timezone is set to `America/New_York`**.
- [ ] `formatBusinessTime("2026-08-03T23:30:00+00:00", "Africa/Tunis")` → `04 Aug · 00:30`
      (hourCycle h23 — never `24:30`).
- [ ] `formatBusinessTime(null, "Africa/Tunis")` and `formatBusinessTime("nonsense", …)` → `—`.
- [ ] `priorityLabel(1)` → `null`; `priorityLabel(3)` → `"P3"`.
- [ ] `scopeTotal("cancelled", stats)` → `null`.

### 7.3 Live E2E

- [ ] `/callbacks` without a session redirects to `/login`.
- [ ] Pending scope lists rows; order matches `priority_level DESC, scheduled_time ASC` — verify
      against a direct SQL query, and confirm the client does **not** re-sort.
- [ ] A pending row with `scheduled_time` in the past shows the **Overdue** chip; the same row in the
      Completed scope after closing shows **Resolved**.
- [ ] **No status cell is ever blank** across all five scopes.
- [ ] Overdue scope returns a subset of Pending, and every row in it shows the Overdue chip.
- [ ] **All scope** returns rows of mixed status — confirm the outgoing request carries `status=`
      (empty), not `status=pending`, in the network trace. *(This is the F1 acceptance test.)*
- [ ] Search filters on caller name, masked-source phone digits, advisor name and reason; a gibberish
      query shows `EmptyState`; clearing restores.
- [ ] Outcome → **Reached**: RPC fires, row leaves Pending, appears in Completed with `completed_at`
      set in the DB, `pending` counter decrements.
- [ ] Outcome → **No answer**: row **stays** in Pending, `assigned_advisor_id` becomes NULL in the DB,
      the advisor cell reads "Unassigned", and `attempts` is **unchanged**. *(F6 acceptance test.)*
- [ ] Submitting an outcome with a blank note leaves any pre-existing `outcome_note` intact in the DB.
      *(F7.)*
- [ ] Cancel: row moves to Cancelled with the Closed chip; no action buttons on that row afterwards.
- [ ] Completed and cancelled rows expose **no** Outcome/Cancel buttons.
- [ ] Counters refresh after every mutation (both list and stats invalidated).
- [ ] Limit control 100 → 250 refetches and the footer truncation notice appears/disappears correctly
      when the queue exceeds the limit. *(F14.)*
- [ ] Set the OS/browser timezone to `America/New_York`: every scheduled time is **identical** to the
      Africa/Tunis run, and matches what `/availability` shows for the same hour. *(F3.)*
- [ ] Stop `docker-compose-business-api-1` → `TableErrorRow` with "Try again"; start it → retry
      recovers.
- [ ] With the API up but coverage failing, the caption reads "business timezone unavailable" rather
      than silently rendering UTC as if it were local.
- [ ] **Zero direct browser requests to `:8108`.**
- [ ] A callback whose advisor was deleted (`ondelete="SET NULL"`) renders "Unassigned" without error.

---

## 8. Open items

### 8.1 A config endpoint for the business timezone — needs your call

The page currently learns `CALLBACK_TIMEZONE` from `GET /api/v1/advisors/coverage`, which is a
supervision report being fetched for one string. A three-line `GET /api/v1/config` returning
`{ timezone, slot_minutes, day_start_hour, day_end_hour }` would be cleaner, is purely additive, and
exposes only existing configuration — squarely inside your rule 3(c). I did **not** build it, because
Feature 3 ships without it. Say the word and it becomes a two-file patch.

### 8.2 The meaning of `priority_level` — needs your call

It is an unconstrained integer with no defined scale, and `reserve()` always writes `1`. Nothing in
the repository ever writes another value. If you define a scale (say 1 normal / 2 elevated / 3 VIP), I
will map it onto `PriorityMeter` and the existing `LEVEL_TONE` table. Until then it renders as `P{n}`.

> Related: `Customer.vip_flag` exists in `crm.customers` but is **not** exposed by the callback
> serializer, so VIP status cannot be shown in this queue without a backend change.

### 8.3 Reassignment is genuinely missing (flagged, not built)

A supervisor cannot move a callback from one advisor to another. This is missing business logic, not a
missing UI. Implementing it would mean a new `PATCH /callbacks/{id}` that validates the target advisor
is actually working at `scheduled_time` (otherwise it would create exactly the false promise
`_pick_advisor` exists to prevent). Per your rule 3, I am flagging rather than building.

### 8.4 Manual booking is blocked by customer lookup (flagged, not built)

Booking needs a customer, and there is no way to search customers — only `GET /customers/{id}/360`.
An additive `GET /api/v1/customers?search=` (name / phone / national_id, exposing the existing
`SupervisionRepository`) would unblock it. Note that the booking flow would also need to pre-flight
through `/callbacks/check`, since `/reserve` collapses four refusal causes into one 409 (F10).

### 8.5 `session_id` → call record

Every callback may link to a `CallSession`, and `GET /api/v1/sessions/{id}` already returns the masked
transcript, sentiment timeline and disposition. That belongs to the Call-logs cookbook; when it lands,
the caller cell here becomes a link and this queue stops being a dead end.

### 8.6 No pagination

`list_callbacks` has `limit` but **no `offset`**. Beyond raising the limit there is no way to page. If
production queues routinely exceed a few hundred rows, an additive `offset` parameter is the smallest
possible change.

### 8.7 Inherited from Feature 2

The queue's capacity, and therefore everything the agent can promise, still depends on
`is_on_call = true`. An advisor removed from the rota keeps their existing assigned callbacks (nothing
reassigns them) but contributes no new capacity. The rota caption on `/availability` remains the place
that explains this.
