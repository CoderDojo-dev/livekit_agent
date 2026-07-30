# Version 71 — Advisor Schedule Engine, Slot-by-Slot Capacity, Time Parsing

> **Base branch:** `version_70`
> **Files changed:** 5 modified, 4 new (+835 / -35)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **New env vars:** `CALLBACK_TIMEZONE` (default `Africa/Tunis`)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### 1. Advisor Schedule Engine (`business_api/availability.py` — NEW)
- `ScheduleIndex` — an in-memory snapshot of who works when, built from three cheap queries.
  - `is_available(advisor_id, moment)` — True only when a weekly shift covers the moment AND no dated exception removes the advisor.
  - `capacity_at(moment)` — how many callbacks a given instant can hold.
  - `available_advisors(moment)` — list of advisors actually working at that instant.
- `load_schedule()` — loads from DB with optional `skill_tag` and `language` filters.
- Shift CRUD: `replace_shifts()` (wholesale, overlap-rejected), `list_shifts()`.
- Time-off CRUD: `create_time_off()`, `delete_time_off()`, `list_time_off()`.
- `coverage_report()` — hour-by-hour coverage for the next N days, including uncovered gaps.
- Business timezone from `CALLBACK_TIMEZONE` env var (default `Africa/Tunis`).

### 2. Per-Instant Capacity (`callbacks.py`)
- `_slot_capacity()` now accepts a `moment` parameter and derives capacity from the `ScheduleIndex`.
- `free_slots()` supports `day` (YYYY-MM-DD) for "what have you got on Thursday?", `skill_tag`, and `language` filters.
- `check_slot()` (NEW) — answers "is this exact time bookable?" with a machine-readable reason (`closed`, `full`, `too_soon`) and nearest real alternatives. This is what makes the negotiation honest: the agent proposes only times the API returned.
- `reserve()` re-verifies capacity under `pg_advisory_xact_lock` at booking time.

### 3. Callback Time Parsing (`callback_schedule_task.py`)
- `parse_requested_time()` — deterministic parser that turns caller speech ("jeudi vers 14h", "le 31/07", "demain matin") into an ISO instant. Returns `None` on ambiguity (safe failure).
- `request_other_time` tool refactored: calls `check_time()` on the API, which replies with availability + alternatives.
- Localized rejection messages per reason (`closed`, `full`, `too_soon`) in fr/ar/en.
- Localized "and" (`_JOIN`) for multi-channel confirmation.
- Caller's exact words passed as `preferred_time` (no pre-parsing by the LLM).

### 4. Callback Client (`callback_client.py`)
- `free_slots()` now accepts `day`, `skill_tag` params.
- New `check_time(requested, skill_tag)` method — asks the API about one precise instant.

### 5. Advisor Schedule + Time-Off Models (`routing.py`)
- **`AdvisorShift`** — recurring weekly working window (weekday, start_minute, end_minute, is_active). Minutes-since-midnight for integer arithmetic in both SQL and Python.
- **`AdvisorTimeOff`** — dated exception (starts_at, ends_at, reason). Separate from shifts for auditability.
- Both under `routing` schema with `ForeignKey` to `Advisor`.

### 6. Admin Dashboard API (`main.py`)
- `GET /api/v1/advisors/coverage` — hour-by-hour coverage report.
- `GET|PUT /api/v1/advisors/{id}/schedule` — read/replace an advisor's weekly grid.
- `GET|POST /api/v1/advisors/{id}/time-off` — list/create absences.
- `DELETE /api/v1/advisors/time-off/{id}` — cancel an absence.
- `GET /api/v1/callbacks/check` — slot availability check.
- `GET /api/v1/callbacks/slots` — now supports `day`, `skill_tag`, `language`.
- CORS extended to `PATCH`, `PUT`, `DELETE`.

### New Files (4)

| File | Purpose |
|------|---------|
| `business_api/availability.py` | ScheduleIndex, load_schedule, shift/time-off CRUD, coverage report |
| `tests/callback/test_time_parsing.py` | 5 tests for `parse_requested_time()` |
| `business-api/tests/test_availability.py` | 5 tests for ScheduleIndex + helpers |
| `docs/versions/version_71.md` | Version doc |
