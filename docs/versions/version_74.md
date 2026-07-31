# Version 74 — Advisor Instant-Level Booking Guard, Truthful Coverage Report

> **Base branch:** `version_73`
> **Files changed:** 2 modified, 2 tests updated/enriched (+64 / -9)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| mcp dependency     | `mcp==1.29.0` (inherited from v73, unchanged) |

---

## What's New

### 1. An advisor can never be booked twice on the same instant (`callbacks.py`)
`_pick_advisor()` used day-level load as the tie-break, but that could not arbitrate the instant
itself: with two advisors and two back-to-back bookings at `13:00`, day-load tie-break re-picked
the same (least-loaded) advisor twice, leaving one caller with nobody and a second slot booked
onto a person already on the phone.

Now the candidates are filtered **per-instant**: every advisor with an OPEN callback at exactly
`when` is excluded before the day-load tie-break runs. If nobody remains, the booking is refused.
This also makes the `remaining` count truthful — the last free unit of capacity can no longer
belong to somebody already booked at that minute.

### 2. Business hours live in one place (`availability.py`)
`DAY_START_HOUR` / `DAY_END_HOUR` moved from `callbacks.py` into `availability.py`, next to the
timezone they are expressed in. The coverage report now measures the **same 08:00-18:00 day the
queue sells** — reporting 18:00-20:00 as "uncovered" described hours nobody was ever going to work.

### 3. Truthful `uncovered_by_language` (`availability.py`)
The per-language gap list was accumulated under the wrong name (`covered_by_language`); renamed
to `uncovered_by_language` so the API field means what it says, with the window fix above making
its contents honest.

---

## Tests

| Test | Verifies |
|------|----------|
| `test_three_reservations_on_the_same_instant_refuse_the_third` | 2 advisors, 3 bookings at `13:00`: first two succeed with **different** advisors, the third is refused — day-load alone would re-pick the least-loaded advisor twice |
| `test_slot_bounds_timezone` | imports follow the constants' new home (`availability`) |

---

## Validation

- Full suites green on the committed tree (business-api 24, agent-worker 74, notification-service 10).
- SQL cleanup: the v73 `smoke-test` reservation was removed after live validation (0 remaining).

---

## Out of Scope (left open, unchanged)

- IdentityVerificationTask `GATE_TIMEOUT_S=40` > `TASK_DEADLINE_S=30`
- policy-service 500 on `evaluate-action` with `identity_expires_at` set — **fixed in version_75**
- `knowledge_search` ToolError; escalation vocabulary duplication; `MAX_OFFERS=3` vs spec `2`
- `test_chaos_wiring.py` 5→4 tests; Twilio SIP (`SIP_TRANSFER_ENABLED`)
- Pre-existing ruff findings (F401/B905/RUF007/I001)
