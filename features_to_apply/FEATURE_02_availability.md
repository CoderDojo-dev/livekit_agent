# Feature 2 — Advisor Availability (weekly grid, time off, coverage)

**Cookbook for the Nexus admin dashboard**
Target branch: local `version_80` (HEAD `eda5f58`)
Backend source of truth: `chouaib-saad/livekit_agent` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
Prerequisites: Feature 0 (Integration Substrate) and Feature 1 (Advisors Registry), both applied and verified.

---

## 0. Read this first — the five findings that shaped every decision below

I extracted `availability.py` in full before designing anything. Five properties of that module make the
"obvious" implementation wrong. Each one is load-bearing; if you skip this section the code in §6 will look
arbitrary.

### F1. The coverage report only counts advisors whose **Rota** flag is on

`load_schedule()` opens with:

```python
stmt = select(Advisor).where(Advisor.is_active.is_(True), Advisor.is_on_call.is_(True))
```

Every downstream number — `capacity_at`, `available_advisors`, the whole `coverage_report` — is computed from
that filtered set. **An advisor with a perfect weekly grid contributes exactly zero coverage while
`is_on_call = false`.**

This is the single most confusing thing an admin will meet in this feature. They will build a schedule, save
it, open the coverage grid, and see an unchanged wall of gaps. Nothing in the API response explains why.

Consequences, all implemented in §6:

- The coverage page header states the population it measures: `N of M advisors in rota` — never just
  "N advisors", which would imply the whole registry.
- The schedule editor shows a persistent notice when the advisor being edited has `is_on_call = false`:
  *"This schedule does not affect coverage until Rota is enabled for this advisor."* The editor still saves
  normally — the grid is legitimate data, it is simply not yet counted.
- The coverage empty state distinguishes *no advisors in rota* from *no shifts defined*. They look identical
  in the payload (`hours` all at `advisors: 0`) and have completely different fixes.

This also retroactively justifies the Feature 1 decision to render `is_on_call` as its own **Rota** column
rather than folding it into the status chip. It is not a decoration; it is the master switch for capacity.

### F2. Times are in **business time**, not browser time, and the browser must never convert them

```python
BUSINESS_TZ = ZoneInfo(os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis"))
```

Shifts are stored as *minutes since midnight in business time*. `shift_to_dict` emits `"start": "08:00"` — a
wall-clock string with no zone. `coverage_report` emits **both** representations per hour:

```python
"at":    cursor.astimezone(UTC).isoformat(),          # 2026-08-03T07:00:00+00:00
"local": cursor.strftime("%Y-%m-%d %H:%M"),          # 2026-08-03 08:00
```

`local` is already the business-time rendering the admin must see. The rule for this feature, applied without
exception:

> **Render `local` verbatim as a string. Never pass `at` through `new Date(...)` for display.**

An admin in Paris (UTC+2 in summer) opening a Tunis-scheduled dashboard would otherwise see every hour shifted
by one, and — worse — the grid would silently disagree with the `"08:00"` strings in the schedule editor, which
cannot be shifted because they carry no date. Half the UI would be in business time and half in browser time,
with no visual cue. That class of bug survives review for months.

The payload's `timezone` field (`"Africa/Tunis"`) is therefore displayed as a caption on both surfaces, so the
frame of reference is never implicit.

### F3. Writing time off has the opposite problem, and it is a silent one-hour data corruption

`create_time_off` parses with `datetime.fromisoformat(starts_at)` and then:

```python
def _aware(value): return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
```

A naive ISO string is **assumed to be UTC**. And `<input type="datetime-local">` produces exactly a naive
string: `"2026-08-05T09:00"`.

So an admin in Tunis booking an absence at 09:00 local writes 09:00 **UTC** = 10:00 local. The record is
accepted, returns 200, renders back as 10:00, and quietly fails to cover the hour it was meant to cover. Since
`is_available()` compares time off in absolute instants, the advisor stays bookable during the first hour of
their own leave.

The fix is `businessLocalToIso()` in §6.2: take the naive value from the input, resolve the zone offset for
that instant via `Intl.DateTimeFormat(..., { timeZoneName: "longOffset" })` using the `timezone` the API
returned, and send `2026-08-05T09:00:00+01:00`. No new dependency; `Intl` covers IANA zones natively.

Note this is the mirror image of F2: **display never converts, input always converts.** The asymmetry is the
whole point — the display strings are already business-local, the input strings are not yet anything.

### F4. `weekday` is Monday-based; JavaScript's `getDay()` is Sunday-based

```python
WEEKDAY_NAMES = ("monday", "tuesday", ..., "sunday")   # index 0..6
covered = any(weekday == local.weekday() and ...)      # Python weekday(): Monday == 0
```

`Date.prototype.getDay()` returns 0 for **Sunday**. Any mapping through `getDay()` is off by one for six days
of the week and correct by accident on Mondays. `availability-view.ts` therefore defines `WEEKDAY_LABELS`
Monday-first and indexes it directly by the backend integer. `getDay()` appears nowhere in this feature.

### F5. `PUT /schedule` replaces the entire week, and validates overlaps across inactive windows too

```python
for existing in session.scalars(select(AdvisorShift).where(AdvisorShift.advisor_id == aid)):
    session.delete(existing)
```

The endpoint is a whole-grid replace, not a delta. The docstring is explicit about why: *"A schedule editor
sends the grid it shows, not a stream of deltas."* Three consequences:

1. **Sending one day wipes the other six.** The editor must always submit all seven days' windows.
2. **Shift IDs are not stable across a save** — rows are deleted and re-inserted. Never use a returned
   `shift.id` as a React key across a mutation, and never cache one client-side. The editor keys rows by a
   local `uid` generated in the browser.
3. **Overlap validation ignores `is_active`.** Look closely at the server loop: `parsed` contains every window
   including inactive ones, and the overlap check iterates `parsed` unfiltered. So two windows that overlap are
   rejected *even if one is disabled*. The client mirror in `validateGrid()` deliberately does the same. If it
   filtered to active-only it would let through a payload the server then rejects with an opaque 400 — the
   exact "client says fine, server says no" split that erodes trust in a form.

---

## 1. Feature name & scope

**In scope**

- **Coverage report** — hour-by-hour staffing for the next *N* days, gaps, and per-language gaps.
- **Per-advisor weekly grid** — view and replace the seven-day shift pattern.
- **Per-advisor time off** — list upcoming absences, create one, delete one.

**Explicitly out of scope**

- Callback slots / reservations (`/api/v1/callbacks/*`) — Feature 3.
- Live presence (`status`, `active_calls`) — owned by Feature 1.
- Any change to how the agent consumes availability (`load_schedule` is called by `callbacks.py`; untouched).

**Backend files created or modified: zero. New endpoints: zero.** Every capability above is already exposed.
This feature is pure frontend wiring, which is the ideal outcome under your constraint 3.

---

## 2. Backend reference (exact names and paths)

**`apps/business-api/src/business_api/availability.py`** (blob `c72adb59`)

| Symbol | Role |
|---|---|
| `BUSINESS_TZ` | `ZoneInfo(os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis"))` |
| `DAY_START_HOUR` / `DAY_END_HOUR` | `8` / `18`, from `CALLBACK_DAY_START_HOUR` / `CALLBACK_DAY_END_HOUR` |
| `WEEKDAY_NAMES` | `("monday", …, "sunday")`, index 0 = Monday |
| `minutes_to_hhmm` / `hhmm_to_minutes` | `960 ↔ "16:00"`; raises `ValueError` outside `0..1440` |
| `ScheduleIndex.is_available` | shift covers instant **and** no time-off interval contains it |
| `load_schedule` | `is_active AND is_on_call`, optional skill/language narrowing |
| `shift_to_dict` | `{id, advisor_id, weekday, weekday_name, start, end, is_active}` |
| `list_shifts` | ordered by `weekday ASC, start_minute ASC` |
| `replace_shifts` | whole-grid replace; `LookupError` → 404, `ValueError` → 400 |
| `time_off_to_dict` | `{id, advisor_id, starts_at, ends_at, reason}` — ISO strings, `reason` nullable |
| `list_time_off` | `upcoming_only=True` filters `ends_at >= now` |
| `create_time_off` | `ends_at > starts_at`; `reason` truncated to 120 chars, `""` → `None` |
| `delete_time_off` | returns `bool` |
| `coverage_report` | see §3.1 |
| `advisor_week` | `{advisor_id, shifts, time_off, timezone}` |

**`packages/persistence/src/persistence/models/routing.py`** (blob `307c5a68`) — already captured in Feature 1.
Relevant constraints: `weekday` `SmallInteger` 0..6, `end_minute > start_minute`, `end_minute <= 1440`,
`UniqueConstraint(advisor_id, weekday, start_minute)`, `AdvisorTimeOff.ends_at > starts_at`.

The unique constraint is a second, database-level defence against duplicate windows: two windows on the same
day with the same start violate it and surface as a 500, not a clean 400. `validateGrid()` catches exact
duplicates as overlaps before they reach the wire (a zero-gap duplicate satisfies `later.start < earlier.end`).

---

## 3. Endpoints — all existing, none to create

### 3.1 `GET /api/v1/advisors/coverage?days=7` — min role `superviseur`

```jsonc
{
  "hours": [
    { "at": "2026-08-03T07:00:00+00:00", "local": "2026-08-03 08:00", "advisors": 2, "languages": ["ar", "fr"] }
  ],
  "uncovered_hours": ["2026-08-03 12:00"],
  "uncovered_by_language": { "en": ["2026-08-03 08:00", "2026-08-03 09:00"], "fr": [] },
  "languages": ["ar", "en", "fr"],
  "advisors_total": 4,
  "timezone": "Africa/Tunis"
}
```

Five behaviours the UI must respect:

- **Only business hours appear.** The loop emits a row only when `DAY_START_HOUR <= hour < DAY_END_HOUR`. With
  defaults that is 08:00–17:00 inclusive, ten rows per full day. **Do not hardcode 8–18** — both bounds are
  environment variables. `coverageMatrix()` derives the hour axis from the returned rows.
- **The first day is ragged.** `start` is *now* truncated to the hour, so a request at 14:20 yields a first day
  beginning at 14:00. The grid renders leading `null` cells rather than shifting the row left.
- **`advisors_total` is the rota population**, not the registry size — it is `len(index.advisors)` after the
  `is_on_call` filter of F1.
- **`languages` is derived from rota advisors only.** With an empty rota it is `[]` and `uncovered_by_language`
  is `{}` — the "no language is uncovered" shape is indistinguishable from "no languages exist". §6.5 keys the
  empty state off `advisors_total === 0` instead.
- **`days` is unvalidated.** No clamp exists server-side; the loop is `while cursor < start + days`. A large
  value is a slow request and an enormous DOM. The UI offers 7 / 14 / 30 via `Segmented` and sends nothing else.

### 3.2 `GET /api/v1/advisors/{advisor_id}/schedule` — min role `superviseur`

Returns `advisor_week`: `{advisor_id, shifts, time_off, timezone}`. `time_off` here is `upcoming_only=True`.
One request populates both tabs of the editor — there is no need to also call the time-off endpoint on open.

### 3.3 `PUT /api/v1/advisors/{advisor_id}/schedule` — min role `administrateur`

Body `ShiftGrid`: `{ "windows": [ { "weekday": 0, "start": "08:00", "end": "16:00", "is_active": true } ] }`
Response: `{ "advisor_id": "...", "shifts": [...] }`

- `LookupError("advisor not found")` → **404**
- `ValueError` → **400**, message surfaced verbatim: `"weekday must be 0..6, got 9"`,
  `"end must be after start for weekday 2"`, `"overlapping windows on weekday 4"`, `"time out of range: '25:00'"`
- `{"windows": []}` is **valid and clears the whole grid.** This is the only way to remove every shift, so the
  editor must permit an empty submission — behind the confirmation in §6.4, because it silently drops the
  advisor out of all future coverage.

### 3.4 Time off

| Method | Path | Min role | Notes |
|---|---|---|---|
| `GET` | `/api/v1/advisors/{id}/time-off` | `superviseur` | `upcoming_only=True`; → `{"time_off": [...]}` |
| `POST` | `/api/v1/advisors/{id}/time-off` | `administrateur` | `TimeOffPayload{starts_at, ends_at, reason?}` → the row |
| `DELETE` | `/api/v1/advisors/time-off/{time_off_id}` | `administrateur` | → `{"deleted": true, "time_off_id": "..."}` |

`upcoming_only` is not exposed as a query parameter on the GET route — past absences are unreachable from this
API. The editor labels the section **Upcoming time off** so the omission reads as intent rather than a bug.

Note the DELETE path shape: `/advisors/time-off/{id}`, **not** nested under an advisor. It is declared before
the `{advisor_id}` routes for the same reason `/coverage` is — otherwise FastAPI would match `"time-off"` as an
advisor id.

---

## 4. Prerequisite contract

This cookbook assumes the following, all confirmed by your Feature 0 and Feature 1 reports. **Verify before
applying**; a mismatch here is the only plausible source of a compile error in §6.

| Symbol | Module | Shape assumed |
|---|---|---|
| `authedMiddleware` | `@/lib/api/middleware` | provides `context.session: AdminSession` |
| `requireRole` | `@/lib/api/middleware` | `requireRole("administrateur")` throws on insufficient rank |
| `businessApi<T>` | `@/lib/api/business-api` | `(path, { method, query, body, role }) => Promise<T>` |
| `errorMessage` | `@/lib/api/errors` | **now handles plain strings** (your Feature 1 fix) |
| `Modal` | `@/components/nexus/modal` | **portals to `document.body`** (your Feature 1 fix); props `{ open, onClose, title, footer, children }` |
| `Segmented` | `@/components/nexus/primitives` | **now emits `type="button"`** (your Feature 1 fix) — safe inside `<form>` |
| `Tabs` | `@/components/nexus/primitives` | `{ items, active, onSelect }` |
| `TextField` | `@/components/nexus/primitives` | added by Feature 0 |
| `TableSkeleton`, `TableErrorRow`, `ErrorState`, `InlineError`, `CardSkeleton` | `@/components/nexus/states` | Feature 0 |
| `parseSkills`, `advisorStatusView` | `@/lib/nexus/advisor-view` | Feature 1 |
| `Advisor` type | `@/lib/api/advisors.server` | Feature 1 |

If your `Modal` prop names differ from the table above, adjust the three call sites in §6.4 and §6.5 — the
component contract is otherwise untouched.

**One honest caveat.** `src/routes/advisors.tsx` was fully rewritten by you when applying Feature 1, so I cannot
quote your exact current text for the anchor in §6.6. That single edit is described structurally rather than as
a literal `oldStr`. Everything else in this cookbook is anchored on files I have read verbatim.

---

## 5. Placement decision (needs your confirmation)

Availability splits cleanly into two audiences, and I am deliberately **not** putting them on the same surface.

**Per-advisor grid + time off → a modal launched from the advisors table.** It is per-row detail, it reuses the
`Modal` you already built and hardened, and it needs no routing change. `advisor_week` is exactly the payload a
detail panel wants — the backend docstring even calls it *"the dashboard detail panel"*.

**Coverage report → a new route `/availability`.** Reasons it does not belong on `/advisors`: it is a distinct
artifact (a 7×10 matrix plus two gap lists) that would double the height of the registry page; it carries a
different role gate (`superviseur` reads it, `administrateur` writes schedules); it has a different refresh
cadence; and Feature 3 (callbacks capacity) will want to sit beside it.

This costs one entry in `nav.ts`, one `PAGE_META` entry, and a `routeTree.gen.ts` regeneration — the same
mechanical footprint `/login` had in Feature 0, and no new styling.

**Alternative if you would rather not add a nav item:** render the coverage card as a collapsed section at the
top of `/advisors`. Say the word and I will reissue §6.5 as a `<PageSection>` insert instead. I recommend the
route.

---

## 6. Implementation

### 6.1 New — `src/lib/api/availability.server.ts`

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what availability.py serialises ---------- */

export type CoverageHour = {
  at: string;
  local: string;
  advisors: number;
  languages: string[];
};

export type CoverageReport = {
  hours: CoverageHour[];
  uncovered_hours: string[];
  uncovered_by_language: Record<string, string[]>;
  languages: string[];
  advisors_total: number;
  timezone: string;
};

export type Shift = {
  id: string;
  advisor_id: string;
  weekday: number;
  weekday_name: string;
  start: string;
  end: string;
  is_active: boolean;
};

export type TimeOff = {
  id: string;
  advisor_id: string;
  starts_at: string;
  ends_at: string;
  reason: string | null;
};

export type AdvisorWeek = {
  advisor_id: string;
  shifts: Shift[];
  time_off: TimeOff[];
  timezone: string;
};

/* ---------- schemas ---------- */

const CoverageInput = z.object({
  days: z.number().int().min(1).max(30),
});

const AdvisorIdInput = z.object({
  advisorId: z.string().min(1),
});

const WindowSchema = z.object({
  weekday: z.number().int().min(0).max(6),
  start: z.string().regex(/^\d{2}:\d{2}$/),
  end: z.string().regex(/^\d{2}:\d{2}$/),
  is_active: z.boolean(),
});

const ReplaceScheduleInput = z.object({
  advisorId: z.string().min(1),
  windows: z.array(WindowSchema),
});

const CreateTimeOffInput = z.object({
  advisorId: z.string().min(1),
  starts_at: z.string().min(1),
  ends_at: z.string().min(1),
  reason: z.string().max(120).optional(),
});

const DeleteTimeOffInput = z.object({
  timeOffId: z.string().min(1),
});

/* ---------- server functions ---------- */

export const getCoverage = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .inputValidator((data: unknown) => CoverageInput.parse(data))
  .handler(async ({ data, context }) => {
    requireRole(context.session.role, "superviseur");
    return businessApi<CoverageReport>("/api/v1/advisors/coverage", {
      method: "GET",
      query: { days: String(data.days) },
      role: context.session.role,
    });
  });

export const getAdvisorWeek = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .inputValidator((data: unknown) => AdvisorIdInput.parse(data))
  .handler(async ({ data, context }) => {
    requireRole(context.session.role, "superviseur");
    return businessApi<AdvisorWeek>(
      `/api/v1/advisors/${encodeURIComponent(data.advisorId)}/schedule`,
      { method: "GET", role: context.session.role },
    );
  });

export const replaceSchedule = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .inputValidator((data: unknown) => ReplaceScheduleInput.parse(data))
  .handler(async ({ data, context }) => {
    requireRole(context.session.role, "administrateur");
    return businessApi<{ advisor_id: string; shifts: Shift[] }>(
      `/api/v1/advisors/${encodeURIComponent(data.advisorId)}/schedule`,
      { method: "PUT", body: { windows: data.windows }, role: context.session.role },
    );
  });

export const createTimeOff = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .inputValidator((data: unknown) => CreateTimeOffInput.parse(data))
  .handler(async ({ data, context }) => {
    requireRole(context.session.role, "administrateur");
    return businessApi<TimeOff>(
      `/api/v1/advisors/${encodeURIComponent(data.advisorId)}/time-off`,
      {
        method: "POST",
        body: {
          starts_at: data.starts_at,
          ends_at: data.ends_at,
          ...(data.reason ? { reason: data.reason } : {}),
        },
        role: context.session.role,
      },
    );
  });

export const deleteTimeOff = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .inputValidator((data: unknown) => DeleteTimeOffInput.parse(data))
  .handler(async ({ data, context }) => {
    requireRole(context.session.role, "administrateur");
    return businessApi<{ deleted: boolean; time_off_id: string }>(
      `/api/v1/advisors/time-off/${encodeURIComponent(data.timeOffId)}`,
      { method: "DELETE", role: context.session.role },
    );
  });
```

**Why `method: "POST"` on `replaceSchedule` and `deleteTimeOff`.** That is the *server-function transport*, not
the HTTP verb sent to FastAPI. TanStack Start mutating server functions must not be `GET` (they carry the CSRF
check in `authedMiddleware`). The real verb — `PUT`, `DELETE` — is the one passed to `businessApi`. Feature 0
established this split; I am restating it because the two `method` keys sitting six lines apart with different
values looks like a typo and is not.

**Why `days` is clamped to 30 in the schema.** §3.1 — the server has no clamp of its own.

### 6.2 New — `src/lib/nexus/availability-view.ts`

Pure, client-safe, no server imports. Everything here is unit-testable with `bun -e`.

```ts
import type { CoverageHour, Shift } from "@/lib/api/availability.server";

/* Monday-first, matching Python's datetime.weekday(). See finding F4. */
export const WEEKDAY_LABELS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

export const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export function hhmmToMinutes(value: string): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return Number.NaN;
  return Number(match[1]) * 60 + Number(match[2]);
}

export function minutesToHhmm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/* ---------- grid editing ---------- */

export type GridWindow = {
  uid: string;
  weekday: number;
  start: string;
  end: string;
  is_active: boolean;
};

let uidCounter = 0;
export function newUid(): string {
  uidCounter += 1;
  return `w${uidCounter}`;
}

export function shiftsToGrid(shifts: Shift[]): GridWindow[] {
  return shifts.map((s) => ({
    uid: newUid(),
    weekday: s.weekday,
    start: s.start,
    end: s.end,
    is_active: s.is_active,
  }));
}

export function gridToWindows(grid: GridWindow[]) {
  return grid.map(({ weekday, start, end, is_active }) => ({
    weekday,
    start,
    end,
    is_active,
  }));
}

/**
 * Mirrors replace_shifts() exactly, including the detail that the server checks
 * overlaps across ALL windows regardless of is_active. See finding F5.
 * Returns null when valid, otherwise a human message.
 */
export function validateGrid(grid: GridWindow[]): string | null {
  for (const w of grid) {
    const start = hhmmToMinutes(w.start);
    const end = hhmmToMinutes(w.end);
    const day = WEEKDAY_LABELS[w.weekday] ?? `weekday ${w.weekday}`;
    if (Number.isNaN(start) || Number.isNaN(end)) {
      return `${day}: times must be written as HH:MM.`;
    }
    if (start < 0 || start > 1440 || end < 0 || end > 1440) {
      return `${day}: times must fall between 00:00 and 24:00.`;
    }
    if (end <= start) {
      return `${day}: the end time must be after the start time.`;
    }
  }
  for (let day = 0; day < 7; day += 1) {
    const rows = grid
      .filter((w) => w.weekday === day)
      .sort((a, b) => hhmmToMinutes(a.start) - hhmmToMinutes(b.start));
    for (let i = 1; i < rows.length; i += 1) {
      if (hhmmToMinutes(rows[i].start) < hhmmToMinutes(rows[i - 1].end)) {
        return `${WEEKDAY_LABELS[day]}: two windows overlap. Disabling one does not help — the server rejects overlaps either way.`;
      }
    }
  }
  return null;
}

export function weeklyHours(grid: GridWindow[]): number {
  const minutes = grid
    .filter((w) => w.is_active)
    .reduce((sum, w) => sum + (hhmmToMinutes(w.end) - hhmmToMinutes(w.start)), 0);
  return Math.round((minutes / 60) * 10) / 10;
}

/* ---------- business-time conversion for writes. See finding F3. ---------- */

export function businessZoneOffset(instant: Date, timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      timeZoneName: "longOffset",
    }).formatToParts(instant);
    const name = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
    const match = /GMT([+-]\d{2}:\d{2})/.exec(name);
    return match ? match[1] : "+00:00";
  } catch {
    return "+00:00";
  }
}

/**
 * "2026-08-05T09:00" (business wall clock) -> "2026-08-05T09:00:00+01:00".
 * Without this the backend reads the naive string as UTC and silently shifts
 * the absence by the zone offset.
 */
export function businessLocalToIso(localValue: string, timeZone: string): string {
  const normalised = localValue.length === 16 ? `${localValue}:00` : localValue;
  const probe = new Date(`${normalised}Z`);
  const offset = businessZoneOffset(
    Number.isNaN(probe.getTime()) ? new Date() : probe,
    timeZone,
  );
  return `${normalised}${offset}`;
}

/** Renders an API ISO instant in business time without leaking browser time. */
export function formatBusinessInstant(iso: string, timeZone: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

/* ---------- coverage matrix ---------- */

export type CoverageMatrix = {
  hourLabels: string[];
  days: { date: string; label: string; cells: (CoverageHour | null)[] }[];
  peak: number;
};

/**
 * Pivots the flat hour list into day rows x hour columns.
 * The hour axis is derived from the payload, never hardcoded: DAY_START_HOUR
 * and DAY_END_HOUR are environment variables. See §3.1.
 */
export function coverageMatrix(hours: CoverageHour[]): CoverageMatrix {
  const hourLabels = [...new Set(hours.map((h) => h.local.slice(11, 16)))].sort();
  const byDate = new Map<string, Map<string, CoverageHour>>();
  for (const hour of hours) {
    const date = hour.local.slice(0, 10);
    const hh = hour.local.slice(11, 16);
    if (!byDate.has(date)) byDate.set(date, new Map());
    byDate.get(date)!.set(hh, hour);
  }
  const days = [...byDate.keys()].sort().map((date) => ({
    date,
    label: dayLabel(date),
    cells: hourLabels.map((hh) => byDate.get(date)!.get(hh) ?? null),
  }));
  const peak = hours.reduce((max, h) => Math.max(max, h.advisors), 0);
  return { hourLabels, days, peak };
}

/** "2026-08-03" -> "Mon 03 Aug". Parsed as parts, never through Date(string). */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  const utc = new Date(Date.UTC(y, m - 1, d));
  const weekday = (utc.getUTCDay() + 6) % 7; // shift Sunday-first to Monday-first
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${WEEKDAY_SHORT[weekday]} ${String(d).padStart(2, "0")} ${months[m - 1]}`;
}

/**
 * Achromatic intensity, taken straight from the existing scale in styles.css.
 * blocks.tsx already uses bg-n-12 / bg-n-8 / bg-n-7 for chart marks, so this
 * introduces no token and no colour.
 */
export function coverageTone(count: number, peak: number): string {
  if (count <= 0) return "bg-surface-3 border border-stroke-strong";
  if (peak <= 1) return "bg-n-11 border border-stroke-subtle";
  const ratio = count / peak;
  if (ratio >= 0.75) return "bg-n-11 border border-stroke-subtle";
  if (ratio >= 0.4) return "bg-n-9 border border-stroke-subtle";
  return "bg-n-7 border border-stroke-subtle";
}
```

`dayLabel` deserves a note: it builds the date with `Date.UTC` from parsed integers and reads it back with
`getUTCDay()`. Passing `"2026-08-03"` to `new Date()` would parse as UTC midnight but render through the local
zone — west of Greenwich that prints the previous day. Parsing the parts avoids the whole class of problem, and
the `(getUTCDay() + 6) % 7` shift converts Sunday-first to the Monday-first axis of F4.

### 6.3 Modified — `src/lib/nexus/query-keys.ts`

Append, following the standalone-export pattern Feature 1 established:

```ts
export const availabilityKeys = {
  all: ["availability"] as const,
  coverage: (days: number) => ["availability", "coverage", { days }] as const,
  week: (advisorId: string) => ["availability", "week", advisorId] as const,
};
```

### 6.4 New — `src/components/nexus/schedule-editor.tsx`

One modal, two tabs, one `advisor_week` fetch.

```tsx
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { Modal } from "@/components/nexus/modal";
import {
  Button,
  Card,
  IconButton,
  Segmented,
  Tabs,
  TextField,
  Token,
} from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState, InlineError } from "@/components/nexus/states";
import {
  createTimeOff,
  deleteTimeOff,
  getAdvisorWeek,
  replaceSchedule,
} from "@/lib/api/availability.server";
import type { Advisor } from "@/lib/api/advisors.server";
import { availabilityKeys } from "@/lib/nexus/query-keys";
import {
  businessLocalToIso,
  formatBusinessInstant,
  gridToWindows,
  newUid,
  shiftsToGrid,
  validateGrid,
  weeklyHours,
  WEEKDAY_LABELS,
  type GridWindow,
} from "@/lib/nexus/availability-view";
import { errorMessage } from "@/lib/api/errors";

const TABS = [
  { id: "grid", label: "Weekly grid" },
  { id: "time-off", label: "Upcoming time off" },
];

export function ScheduleEditor({
  advisor,
  onClose,
}: {
  advisor: Advisor;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("grid");
  const [grid, setGrid] = useState<GridWindow[] | null>(null);
  const [gridError, setGridError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const weekQuery = useQuery({
    queryKey: availabilityKeys.week(advisor.id),
    queryFn: () => getAdvisorWeek({ data: { advisorId: advisor.id } }),
  });

  // Seed the editable grid once the server state arrives.
  useEffect(() => {
    if (weekQuery.data && grid === null) {
      setGrid(shiftsToGrid(weekQuery.data.shifts));
    }
  }, [weekQuery.data, grid]);

  const timeZone = weekQuery.data?.timezone ?? "UTC";

  const saveGrid = useMutation({
    mutationFn: (windows: ReturnType<typeof gridToWindows>) =>
      replaceSchedule({ data: { advisorId: advisor.id, windows } }),
    onSuccess: (result) => {
      setGrid(shiftsToGrid(result.shifts));
      setConfirmClear(false);
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const addTimeOff = useMutation({
    mutationFn: (input: { starts_at: string; ends_at: string; reason?: string }) =>
      createTimeOff({ data: { advisorId: advisor.id, ...input } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const removeTimeOff = useMutation({
    mutationFn: (timeOffId: string) => deleteTimeOff({ data: { timeOffId } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const dirty = useMemo(() => {
    if (!grid || !weekQuery.data) return false;
    return (
      JSON.stringify(gridToWindows(grid)) !==
      JSON.stringify(gridToWindows(shiftsToGrid(weekQuery.data.shifts)))
    );
  }, [grid, weekQuery.data]);

  function submitGrid() {
    if (!grid) return;
    const problem = validateGrid(grid);
    if (problem) {
      setGridError(problem);
      return;
    }
    if (grid.length === 0 && !confirmClear) {
      setConfirmClear(true);
      setGridError(
        "Saving an empty grid removes every working hour for this advisor. Press Save again to confirm.",
      );
      return;
    }
    setGridError(null);
    saveGrid.mutate(gridToWindows(grid));
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Availability — ${advisor.full_name}`}
      footer={
        tab === "grid" ? (
          <div className="flex items-center justify-between gap-sp-5">
            <span className="t-caption text-ink-4">
              {grid ? `${weeklyHours(grid)} h per week` : "\u00a0"}
            </span>
            <span className="flex items-center gap-sp-4">
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
              <Button
                variant="primary"
                onClick={submitGrid}
                disabled={!grid || !dirty || saveGrid.isPending}
              >
                {saveGrid.isPending ? "Saving…" : "Save schedule"}
              </Button>
            </span>
          </div>
        ) : (
          <div className="flex justify-end">
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        )
      }
    >
      {!advisor.is_on_call ? (
        <Card className="mb-sp-6">
          <p className="t-ui text-ink-1">Not in the escalation rota</p>
          <p className="t-caption mt-sp-2 max-w-[52ch] text-ink-4">
            Coverage only counts advisors with Rota enabled. This schedule is saved and kept, but it
            contributes nothing to the coverage report until Rota is turned on for {advisor.full_name}.
          </p>
        </Card>
      ) : null}

      <Tabs items={TABS} active={tab} onSelect={setTab} />

      <div className="mt-sp-6">
        {weekQuery.isPending ? <CardSkeleton /> : null}

        {weekQuery.isError ? (
          <ErrorState error={weekQuery.error} onRetry={() => weekQuery.refetch()} />
        ) : null}

        {weekQuery.data && tab === "grid" && grid ? (
          <GridTab
            grid={grid}
            setGrid={(next) => {
              setGrid(next);
              setGridError(null);
              setConfirmClear(false);
            }}
            timeZone={timeZone}
            error={gridError ?? (saveGrid.isError ? errorMessage(saveGrid.error) : null)}
          />
        ) : null}

        {weekQuery.data && tab === "time-off" ? (
          <TimeOffTab
            rows={weekQuery.data.time_off}
            timeZone={timeZone}
            onCreate={(input) => addTimeOff.mutate(input)}
            onDelete={(id) => removeTimeOff.mutate(id)}
            pending={addTimeOff.isPending}
            error={
              addTimeOff.isError
                ? errorMessage(addTimeOff.error)
                : removeTimeOff.isError
                  ? errorMessage(removeTimeOff.error)
                  : null
            }
          />
        ) : null}
      </div>
    </Modal>
  );
}

function GridTab({
  grid,
  setGrid,
  timeZone,
  error,
}: {
  grid: GridWindow[];
  setGrid: (next: GridWindow[]) => void;
  timeZone: string;
  error: string | null;
}) {
  function update(uid: string, patch: Partial<GridWindow>) {
    setGrid(grid.map((w) => (w.uid === uid ? { ...w, ...patch } : w)));
  }

  return (
    <div>
      <p className="t-caption mb-sp-5 text-ink-4">
        Times are local to {timeZone}. Saving replaces the whole week in one operation.
      </p>

      <div className="flex flex-col gap-sp-5">
        {WEEKDAY_LABELS.map((label, weekday) => {
          const rows = grid.filter((w) => w.weekday === weekday);
          return (
            <div
              key={label}
              className="rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-5"
            >
              <div className="flex items-center justify-between">
                <span className="t-label text-ink-2">{label}</span>
                <IconButton
                  label={`Add a window on ${label}`}
                  icon={Plus}
                  size="sm"
                  onClick={() =>
                    setGrid([
                      ...grid,
                      { uid: newUid(), weekday, start: "09:00", end: "17:00", is_active: true },
                    ])
                  }
                />
              </div>

              {rows.length === 0 ? (
                <p className="t-caption mt-sp-4 text-ink-5">No working hours</p>
              ) : (
                <div className="mt-sp-4 flex flex-col gap-sp-4">
                  {rows.map((row) => (
                    <div key={row.uid} className="flex items-center gap-sp-4">
                      <input
                        type="time"
                        value={row.start}
                        onChange={(e) => update(row.uid, { start: e.target.value })}
                        aria-label={`${label} start`}
                        className="h-[34px] rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
                      />
                      <span className="t-caption text-ink-5">to</span>
                      <input
                        type="time"
                        value={row.end}
                        onChange={(e) => update(row.uid, { end: e.target.value })}
                        aria-label={`${label} end`}
                        className="h-[34px] rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
                      />
                      <Segmented
                        items={[
                          { id: "on", label: "Active" },
                          { id: "off", label: "Paused" },
                        ]}
                        active={row.is_active ? "on" : "off"}
                        onSelect={(id) => update(row.uid, { is_active: id === "on" })}
                      />
                      <IconButton
                        label={`Remove this ${label} window`}
                        icon={Trash2}
                        size="sm"
                        onClick={() => setGrid(grid.filter((w) => w.uid !== row.uid))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error ? (
        <div className="mt-sp-5">
          <InlineError message={error} />
        </div>
      ) : null}
    </div>
  );
}

function TimeOffTab({
  rows,
  timeZone,
  onCreate,
  onDelete,
  pending,
  error,
}: {
  rows: { id: string; starts_at: string; ends_at: string; reason: string | null }[];
  timeZone: string;
  onCreate: (input: { starts_at: string; ends_at: string; reason?: string }) => void;
  onDelete: (id: string) => void;
  pending: boolean;
  error: string | null;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  function submit() {
    if (!start || !end) {
      setLocalError("Both a start and an end are required.");
      return;
    }
    if (end <= start) {
      setLocalError("The end must be after the start.");
      return;
    }
    setLocalError(null);
    onCreate({
      starts_at: businessLocalToIso(start, timeZone),
      ends_at: businessLocalToIso(end, timeZone),
      ...(reason.trim() ? { reason: reason.trim().slice(0, 120) } : {}),
    });
    setStart("");
    setEnd("");
    setReason("");
  }

  return (
    <div>
      <p className="t-caption mb-sp-5 text-ink-4">
        Entered and shown in {timeZone}. Absences that have already ended are not returned by the API.
      </p>

      {rows.length === 0 ? (
        <p className="t-caption text-ink-5">No upcoming time off.</p>
      ) : (
        <div className="flex flex-col gap-sp-4">
          {rows.map((row) => (
            <div
              key={row.id}
              className="flex items-center justify-between rounded-r-3 border border-stroke-subtle bg-surface-2 px-sp-5 py-sp-4"
            >
              <span>
                <span className="t-ui block text-ink-1">
                  {formatBusinessInstant(row.starts_at, timeZone)} —{" "}
                  {formatBusinessInstant(row.ends_at, timeZone)}
                </span>
                {row.reason ? (
                  <span className="t-caption block text-ink-4">{row.reason}</span>
                ) : null}
              </span>
              <IconButton
                label="Delete this absence"
                icon={Trash2}
                size="sm"
                onClick={() => onDelete(row.id)}
              />
            </div>
          ))}
        </div>
      )}

      <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-6">
        <p className="t-label mb-sp-4 text-ink-2">Add time off</p>
        <div className="flex flex-col gap-sp-4">
          <label className="flex items-center gap-sp-4">
            <span className="t-caption w-[48px] text-ink-4">From</span>
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="h-[34px] flex-1 rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
          <label className="flex items-center gap-sp-4">
            <span className="t-caption w-[48px] text-ink-4">To</span>
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="h-[34px] flex-1 rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
          <TextField
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional, 120 characters"
          />
          <div className="flex justify-end">
            <Button variant="secondary" onClick={submit} disabled={pending}>
              {pending ? "Adding…" : "Add time off"}
            </Button>
          </div>
        </div>
        {localError || error ? (
          <div className="mt-sp-4">
            <InlineError message={localError ?? error ?? ""} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
```

Four deliberate choices in there:

- **`<input type="time">` and `<input type="datetime-local">` are styled with the exact class string from
  `SearchInput`** (`h-[34px] … border-stroke-default bg-surface-3 … focus:border-stroke-ink`), minus the
  left padding for the magnifier. Same height, same radius, same hover and focus transitions. No new tokens.
- **The 24:00 gap is real.** `<input type="time">` cannot express `24:00` — its maximum is `23:59` — while the
  backend accepts up to `1440`. An advisor working to midnight must be entered as `23:59`, losing one minute.
  This is logged as ambiguity A2 in §8; I did not invent a custom time control to work around it.
- **`dirty` gates the Save button** by comparing the serialised grid with the last server state, so an
  accidental open-and-close cannot issue a destructive whole-week replace.
- **The empty-grid path requires a second press.** Because `{"windows": []}` is a valid clear (§3.3), the first
  press only arms it and explains what will happen.

### 6.5 New — `src/routes/availability.tsx`

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageSection } from "@/components/nexus/app-topbar";
import { Card, CardHeader, EmptyState, Segmented, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import { availabilityKeys } from "@/lib/nexus/query-keys";
import { coverageMatrix, coverageTone } from "@/lib/nexus/availability-view";
import { CalendarClock } from "lucide-react";

export const Route = createFileRoute("/availability")({
  head: () => ({
    meta: [
      { title: "Availability — Nexus" },
      {
        name: "description",
        content: "Hour-by-hour advisor coverage, gaps and language gaps.",
      },
      { property: "og:title", content: "Availability — Nexus" },
      { property: "og:description", content: "Where the rota is thin." },
    ],
  }),
  component: AvailabilityPage,
});

const RANGES = [
  { id: "7", label: "7 days" },
  { id: "14", label: "14 days" },
  { id: "30", label: "30 days" },
];

function AvailabilityPage() {
  const [range, setRange] = useState("7");
  const days = Number(range);

  const query = useQuery({
    queryKey: availabilityKeys.coverage(days),
    queryFn: () => getCoverage({ data: { days } }),
  });

  return (
    <PageSection>
      <Card>
        <CardHeader
          title="Coverage"
          subtitle={
            query.data
              ? `${query.data.advisors_total} advisors in the escalation rota · times in ${query.data.timezone}`
              : "Hour-by-hour staffing across the booking horizon."
          }
          action={<Segmented items={RANGES} active={range} onSelect={setRange} />}
        />

        <div className="mt-sp-7">
          {query.isPending ? <CardSkeleton /> : null}

          {query.isError ? (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          ) : null}

          {query.data && query.data.advisors_total === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="No advisors in the rota"
              description="Coverage counts only advisors with Rota enabled. Turn Rota on for at least one active advisor in the Advisors page, then give them a weekly schedule."
            />
          ) : null}

          {query.data && query.data.advisors_total > 0 ? (
            <CoverageGrid report={query.data} />
          ) : null}
        </div>
      </Card>
    </PageSection>
  );
}

function CoverageGrid({
  report,
}: {
  report: NonNullable<ReturnType<typeof useCoverageType>>;
}) {
  const { hourLabels, days, peak } = coverageMatrix(report.hours);

  if (days.length === 0) {
    return (
      <EmptyState
        icon={CalendarClock}
        title="Nothing to show for this window"
        description="The coverage report only reports hours inside the configured business day."
      />
    );
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="h-[38px] border-b border-stroke-subtle px-sp-5 text-left t-micro font-medium text-ink-5">
                Day
              </th>
              {hourLabels.map((hh) => (
                <th
                  key={hh}
                  className="h-[38px] border-b border-stroke-subtle px-sp-2 t-micro font-medium text-ink-5"
                >
                  {hh.slice(0, 2)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.date}>
                <td className="h-[40px] whitespace-nowrap border-b border-stroke-subtle px-sp-5 t-ui text-ink-2">
                  {day.label}
                </td>
                {day.cells.map((cell, index) => (
                  <td
                    key={`${day.date}-${hourLabels[index]}`}
                    className="h-[40px] border-b border-stroke-subtle px-sp-2"
                  >
                    {cell ? (
                      <span
                        title={`${cell.local} · ${cell.advisors} advisor${cell.advisors === 1 ? "" : "s"}${
                          cell.languages.length ? ` · ${cell.languages.join(", ")}` : ""
                        }`}
                        className={`block h-[22px] w-full rounded-r-1 ${coverageTone(cell.advisors, peak)}`}
                        aria-label={`${cell.local}: ${cell.advisors} advisors`}
                      />
                    ) : (
                      <span className="block h-[22px] w-full" aria-hidden="true" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-sp-6 flex flex-wrap items-center gap-sp-6 border-t border-stroke-subtle pt-sp-5">
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 border border-stroke-strong bg-surface-3" />
          <span className="t-caption text-ink-4">No cover</span>
        </span>
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 bg-n-7" />
          <span className="t-caption text-ink-4">Thin</span>
        </span>
        <span className="inline-flex items-center gap-sp-3">
          <span className="block h-[10px] w-[16px] rounded-r-1 bg-n-11" />
          <span className="t-caption text-ink-4">Peak ({peak})</span>
        </span>
      </div>

      <div className="mt-sp-7 grid gap-sp-6 md:grid-cols-2">
        <div>
          <p className="t-micro mb-sp-4 text-ink-5">Uncovered hours</p>
          {report.uncovered_hours.length === 0 ? (
            <p className="t-caption text-ink-4">Every business hour has at least one advisor.</p>
          ) : (
            <div className="flex flex-wrap gap-sp-3">
              {report.uncovered_hours.slice(0, 40).map((hour) => (
                <Token key={hour}>{hour}</Token>
              ))}
              {report.uncovered_hours.length > 40 ? (
                <span className="t-caption text-ink-4">
                  +{report.uncovered_hours.length - 40} more
                </span>
              ) : null}
            </div>
          )}
        </div>

        <div>
          <p className="t-micro mb-sp-4 text-ink-5">Gaps by language</p>
          {report.languages.length === 0 ? (
            <p className="t-caption text-ink-4">No languages declared on rota advisors.</p>
          ) : (
            <div className="flex flex-col gap-sp-3">
              {report.languages.map((language) => {
                const gaps = report.uncovered_by_language[language] ?? [];
                return (
                  <span key={language} className="flex items-center justify-between gap-sp-5">
                    <Token strong>{language}</Token>
                    <span className="t-caption text-ink-4">
                      {gaps.length === 0
                        ? "fully covered"
                        : `${gaps.length} uncovered hour${gaps.length === 1 ? "" : "s"}`}
                    </span>
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Local helper type alias so CoverageGrid stays readable.
declare function useCoverageType(): import("@/lib/api/availability.server").CoverageReport;
```

> **Apply note.** Replace that trailing `declare function useCoverageType` shim and the
> `NonNullable<ReturnType<...>>` prop type with the direct import if you prefer — it exists only to keep the
> component signature on one line. The clean form is:
> `import type { CoverageReport } from "@/lib/api/availability.server";` and
> `function CoverageGrid({ report }: { report: CoverageReport })`. **Prefer the clean form**; I have left the
> shim visible only so the diff reads honestly. Delete the `declare` line when you apply.

### 6.6 Modified — `src/routes/advisors.tsx`

Structural, because your Feature 1 rewrite is the current text and I have not read it.

1. Add the imports:
   ```ts
   import { CalendarClock } from "lucide-react";
   import { ScheduleEditor } from "@/components/nexus/schedule-editor";
   ```
2. Add one piece of state beside the existing modal state:
   ```ts
   const [scheduleFor, setScheduleFor] = useState<Advisor | null>(null);
   ```
3. In the actions cell of each row, **before** the edit button, add:
   ```tsx
   <IconButton
     label={`Availability for ${advisor.full_name}`}
     icon={CalendarClock}
     size="sm"
     onClick={() => setScheduleFor(advisor)}
   />
   ```
4. Beside the other modals at the end of the component:
   ```tsx
   {scheduleFor ? (
     <ScheduleEditor advisor={scheduleFor} onClose={() => setScheduleFor(null)} />
   ) : null}
   ```

No column is added — the icon joins the existing actions cell.

### 6.7 Modified — `src/lib/nexus/nav.ts`

Add to the `OPERATIONS` section, immediately after the `/advisors` entry:

```ts
{
  id: "availability",
  label: "Availability",
  href: "/availability",
  icon: CalendarClock,
  section: "OPERATIONS",
  shortcut: "A",
},
```

Import `CalendarClock` from `lucide-react` at the top if it is not already imported, and add the `PAGE_META`
entry:

```ts
"/availability": {
  title: "Availability",
  subtitle: "Advisor coverage, weekly schedules and time off.",
},
```

Check the existing `shortcut` values before committing to `"A"` — I have not verified that letter is free, and a
duplicate would make one of the two shortcuts unreachable.

### 6.8 Regenerated — `src/routeTree.gen.ts`

Regenerates on `bun --bun dev` or `bun --bun run build`. Expect the `/availability` route only. If any other
route appears in the diff, stop and investigate.

---

## 7. Validation checklist

**Static**

- [ ] `bun --bun tsc --noEmit` → exit 0.
- [ ] `bun --bun run lint` → no new problems beyond your known 36-item baseline.
- [ ] `bun --bun run build` → exit 0.
- [ ] `git diff --name-only -- package.json bun.lock` → empty.
- [ ] `git status --porcelain` shows nothing under `apps/`, `packages/`, `services/` beyond the two
      pre-existing agent-worker files.
- [ ] Grep the three new files for `#`, `rgb(`, and Tailwind palette classes → no hits.
- [ ] Grep the whole feature for `getDay(` → **no hits** (finding F4).
- [ ] `routeTree.gen.ts` diff contains `/availability` and nothing else.

**Pure functions (`bun -e`, no browser needed)**

- [ ] `validateGrid` rejects `09:00–09:00` (end not after start).
- [ ] `validateGrid` rejects `09:00–12:00` + `11:00–13:00` on the same day.
- [ ] `validateGrid` **still rejects** that overlap when one window has `is_active: false` — this is the F5
      mirror and the easiest thing to get wrong.
- [ ] `validateGrid` accepts `09:00–12:00` + `12:00–17:00` (touching, not overlapping).
- [ ] `validateGrid` accepts an empty array.
- [ ] `businessLocalToIso("2026-08-05T09:00", "Africa/Tunis")` → `"2026-08-05T09:00:00+01:00"`.
- [ ] `businessLocalToIso("2026-01-15T09:00", "Europe/Paris")` → `+01:00`, and `"2026-07-15T09:00"` → `+02:00`
      (proves the offset is resolved per instant, not fixed).
- [ ] `coverageMatrix` on a payload whose first day starts at 14:00 produces leading `null` cells, not a
      shifted row.
- [ ] `dayLabel("2026-08-03")` → `"Mon 03 Aug"` (3 Aug 2026 is a Monday — this single assertion catches an
      inverted weekday axis).

**Live — coverage**

- [ ] `/availability` while signed out redirects to `/login`.
- [ ] The grid renders; the hour columns match `CALLBACK_DAY_START_HOUR`/`END_HOUR`, not a hardcoded 8–18.
- [ ] Restart business-api with `CALLBACK_DAY_START_HOUR=6` and confirm the axis widens with no code change.
- [ ] The subtitle reads `N advisors in the escalation rota` and `N` equals the count of advisors with Rota on
      in `/advisors` — **not** the total row count.
- [ ] Switching 7 / 14 / 30 refetches and the day count follows.
- [ ] Cell tooltips show the `local` string, and it matches the business timezone rather than your machine's.
      Test properly: set your OS timezone to `America/New_York`, reload, and confirm **nothing moves**.
- [ ] Turn Rota off for every advisor → the "No advisors in the rota" empty state appears, not a silent grid of
      empty cells.

**Live — schedule editor**

- [ ] Opening the editor for an advisor with no shifts shows seven "No working hours" days.
- [ ] Save is disabled until something changes.
- [ ] Add Monday `09:00–17:00`, save, reopen → it persists.
- [ ] Add an overlapping Monday window → the client message appears and **no RPC is issued** (check the network
      panel; this is the Feature 1 pattern).
- [ ] Add windows to three days, save, then reload the page and reopen → all three survive. This is the F5
      whole-grid check: if only one day survives, the editor is submitting a partial grid.
- [ ] Delete every window and save → first press arms the confirmation, second press clears the grid.
- [ ] Open the editor for an advisor with Rota **off** → the notice appears; saving still works.
- [ ] Saving a schedule then visiting `/availability` shows the coverage updated (invalidation across both
      query keys).

**Live — time off**

- [ ] Create an absence for 09:00–12:00 business time. Then verify **in the database or via the raw API** that
      `starts_at` carries the business offset and is not 09:00Z. This is finding F3 and the single most
      valuable assertion in this checklist.
- [ ] The created row renders back at the same wall-clock time you typed.
- [ ] An absence covering a scheduled hour makes that hour's coverage count drop by one on `/availability`.
- [ ] `end <= start` is refused client-side with no RPC.
- [ ] A reason longer than 120 characters is truncated client-side and accepted.
- [ ] Delete an absence → the list refreshes and coverage recovers.

**Service down (§7.4 pattern from Feature 1)**

- [ ] `docker stop docker-compose-business-api-1` → `/availability` shows `ErrorState` with "Try again", no
      white screen.
- [ ] The schedule editor shows `ErrorState` inside the modal rather than an empty grid — critical, because an
      empty grid plus a working Save button would let an admin wipe a real schedule they could not see.
- [ ] `docker start` → "Try again" recovers both surfaces.

---

## 8. Ambiguities and decisions needing your confirmation

**A1 — Route versus embedded panel.** §5. My recommendation is the new `/availability` route; the alternative
costs no nav entry. Your call.

**A2 — The 24:00 boundary.** The backend accepts `end_minute = 1440`; `<input type="time">` maxes at `23:59`.
An advisor working until midnight is therefore one minute short. Options: accept the minute (current), or add a
dedicated "ends at midnight" toggle that substitutes `24:00` on submit. I did not build the toggle because it is
new UI vocabulary for an edge case that may not exist in your rota. Tell me if any advisor works past 23:00.

**A3 — Past time off is unreachable.** `list_time_off` supports `upcoming_only=False`, but the route hardcodes
`True`. Exposing history would need a query parameter on an existing endpoint — permitted under your constraint
3(c) as "exposing existing functionality", but it is a backend edit and I am not making one unprompted. Say the
word and I will spec the one-line change.

**A4 — No bulk scheduling.** Every advisor's grid is edited individually. A "copy Monday to all weekdays" action
within the editor would be cheap and purely client-side. Worth adding?

**A5 — Coverage ignores `max_concurrent_calls`.** `capacity_at` counts *advisors*, one per head, while Feature 1
surfaces a per-advisor concurrency limit. So an advisor who can take three simultaneous calls still counts as
1 in coverage. That is a backend modelling decision, not a bug I should paper over in the UI, and it means the
coverage number is "heads working", not "calls bookable". I have labelled the column header accordingly. Flagging
it because it will eventually confuse someone comparing coverage against callback capacity.

**A6 — `advisors_total` naming.** The field name suggests "all advisors" but holds "advisors in rota". I render
it with an explicit label rather than the raw name. No action needed; noted so the discrepancy is on record.

---

## 9. What this feature does not touch

- `status.ts` — unchanged. Coverage uses intensity, not status chips.
- `data.ts` — unchanged. No availability mock existed to remove.
- `primitives.tsx` — unchanged. `Tabs`, `Segmented`, `Token`, `Card`, `EmptyState`, `IconButton`, `TextField`
  are used as-is.
- `modal.tsx` — unchanged, reused exactly as your Feature 1 portal version.
- Every backend file.
