# Version 73 — Slot-Grid Contract, Advisor-Bound Reservations, Twilio URL Hardening

> **Base branch:** `version_72`
> **Files changed:** 3 modified, 7 new (+343 / -10)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none (`mcp==1.29.0` pin inherited from v72, unchanged)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| mcp dependency     | `mcp==1.29.0` (inherited from v72, unchanged) |
| Image rebuilds     | `business-api`, `notification-service`, `agent-worker` rebuilt `--no-cache` for live validation (no Dockerfile change) |

---

## What's New

### 1. Twilio REST URL built by concatenation, not f-string (`channels.py`)
**Hardening, not a live bug:** the committed v72 blob `998e5b7e…` was verified clean (single-brace
f-string, URL parses, all tests green on the committed tree — the brace corruption described in
the review doc was in the document itself, not the code). Per the patch decision, the URL is now
built by pure concatenation from `_TWILIO_API_ROOT`, so a transport that doubled braces could
never produce a literal-brace URL again. Anti-regression test added:
`test_no_stray_characters_before_the_scheme`.

### 2. `reserve()` aligned on the slot grid (`callbacks.py`)
A reservation must be minute-aligned on the 30-minute grid with zero sub-minute components.
`13:07` or `13:00:30` is now refused (logged, returns `None`) **before** the advisory lock —
a hand-built payload can no longer store a timestamp no offer or report can produce. TDD:
2 tests in `test_reserve_grid_alignment.py` (red → green).

### 3. Reservations bound to a named advisor from birth (`callbacks.py`)
- `_pick_advisor(session, when, index)` picks the **least-loaded** advisor working that slot
  (load = OPEN callbacks assigned that business day, tie-break `str(id)` deterministic).
- `reserve()` derives capacity from `load_schedule()` → `index.capacity_at()`, then writes
  `assigned_advisor_id` into the row — a booking is a promise that a **specific** person calls.
- `claim_next()` takes an advisor's own callbacks first, then unassigned ones, and never hands
  an assigned callback to another advisor (`wanted` strict filter, commit 8ea95d7).

### 4. Schedule audit + per-language coverage (`availability.py`, `audit_schedule.py`)
- `coverage_report()` now returns `languages` (promised across the staff) and
  `uncovered_by_language` (hours where a promised language has nobody working).
- `scripts/audit_schedule.py`: two SQL audits — weekly hours per advisor and per language
  (ASC order, advisor count per language per the v73 spec).

### 5. Committed-tree test harness (`scripts/`)
- `test_committed.sh` (bash) + `test_committed.ps1` (PowerShell): `git archive REF | tar`
  into a clean temp dir, then run the three suites against the committed tree — the working
  directory is never tested, so a broken URL and a green report can no longer coexist.

---

## Fixes Applied

| Fix | Where | Commit |
|-----|-------|--------|
| Twilio URL immune to brace-corrupting transports (hardening) | `channels.py` + `test_twilio_url.py` | db1b75a |
| Off-grid reservation payloads refused (`13:07`, `13:00:30`) | `callbacks.py::reserve` | db1b75a |
| Booking carries `assigned_advisor_id` (least-loaded pick) | `callbacks.py` | db1b75a |
| `claim_next` never reassigns an owned callback to another advisor | `callbacks.py` | 8ea95d7 |
| Coverage report exposes language gaps | `availability.py` | db1b75a |
| Audit queries match spec (ASC, advisor count) | `audit_schedule.py` | 3c4ffd6 |
| v72 pilot test rows removed from `callback_schedules` | SQL cleanup (`pilot-validation-v72`, `test-reservation-v72%`) | db1b75a |

---

## Validation

- **Committed tree (`test_committed.sh HEAD`)**: 107/107 tests green
  (business-api 23, agent-worker 74, notification-service 10) on `db1b75a`.
- **Live (containers rebuilt --no-cache)**:
  - `GET :8106/health/credentials` → `twilio.ok=true`, `smtp.ok=true`
  - `POST :8106/notify` WhatsApp `+21626078277` → `sent:true`, ref `SM30c038d47ae5d387fbf75b18e9588b62`
  - `POST :8108/api/v1/callbacks/reserve` `13:07` (off-grid) → **409**
  - `POST :8108/api/v1/callbacks/reserve` `13:00` → **201**, `assigned_advisor_name: "Leila Hamdi"`
  - `GET :8108/api/v1/advisors/coverage?days=2` → `languages: ar,en,fr`, `uncovered_by_language` populated
  - smoke-test rows cleaned up (0 remaining)

---

## Out of Scope (left open, unchanged)

- IdentityVerificationTask `GATE_TIMEOUT_S=40` > `TASK_DEADLINE_S=30`
- policy-service 500 on `evaluate-action`; `knowledge_search` ToolError
- Escalation vocabulary duplication; `MAX_OFFERS=3` vs spec `2`
- `test_chaos_wiring.py` 5→4 tests; Twilio SIP (`SIP_TRANSFER_ENABLED`)
- Pre-existing ruff findings (F401/B905/RUF007/I001) and `test_multilingual.py` basename
  collision (suites run in separate pytest invocations by design)
