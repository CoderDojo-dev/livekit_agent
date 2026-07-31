# Version 72 — Callback Counter-Proposal Fix, Local Business Hours, MCP Pin

> **Base branch:** `version_71`
> **Files changed:** 8 modified, 3 new (+180 / -19)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** `mcp==1.29.0` pinned (was unpinned `mcp` — 2.0.0 dropped FastMCP)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| mcp dependency     | Pinned `mcp==1.29.0`     |

---

## What's New

### 1. Fix: Book the Confirmed Counter-Proposal (`callback_schedule_task.py`)
**Regression introduced by v71:** when the caller proposed a time and the API confirmed it as available, the anti-hallucination guard in `_match()` rejected the very instant the business API had just validated — the agent re-offered the previous slots instead of booking the one the caller asked for.

**Fix:** the API-confirmed instant is now written into `self._slots` as the only bookable offer before calling `accept_slot()`, so the guard accepts it and the booking goes through.
- Regression test: `tests/callback/test_counter_proposal.py` — asserts the confirmed instant actually reaches `reserve()`.

### 2. Fix: Local Business Hours in Slot Generation (`callbacks.py`)
**Bug:** `DAY_START_HOUR`/`DAY_END_HOUR` are business-local hours but were compared directly against UTC `cursor.hour`:
- The first local working hour (08:00 Tunis = 07:00 UTC) was silently dropped.
- A late UTC hour could pass the filter when the local hour was already after closing.

**Fix:** the comparison now converts to `BUSINESS_TZ` first: `local_hour = cursor.astimezone(BUSINESS_TZ).hour`.
- Also fixed the slot-boundary rounding from "next boundary" to a true ceiling, so an instant already on a boundary stays put.
- Tests: `tests/test_slot_bounds_timezone.py` — every generated slot is within local business hours, and 08:00 local is actually offered.

### 3. Twilio URL Extraction (`channels.py`)
- `_messages_url(sid)` and `_account_url(sid)` extracted as testable module-level helpers — no literal braces allowed around them.
- Tests in `test_twilio_url.py` extended accordingly.

### 4. Specialist-First Skill Matching (`availability.py`)
- `load_schedule()` with a `skill_tag` now returns **specialists first**, falling back to generalists only when no specialist exists — with a log trace. Previously it returned the union (specialists + generalists), which could fill a slot with a generalist while a specialist was free.

### 5. MCP Dependency Pin (`mcp-servers/messaging-gateway/pyproject.toml`)
- `mcp` pinned to `==1.29.0` — the unpinned `mcp` allowed 2.0.0, which dropped the `mcp.server.fastmcp` module the messaging gateway imports.

### Files Changed (8 modified, 3 new)

| File | Summary |
|------|---------|
| `tasks/callback_schedule_task.py` | Book the API-confirmed counter-proposal |
| `tests/callback/test_counter_proposal.py` **NEW** | Regression test for the v71 guard bug |
| `business_api/availability.py` | Specialist-first skill matching |
| `business_api/callbacks.py` | Local-time business-hours filter, ceiling rounding |
| `business-api/tests/test_slot_bounds_timezone.py` **NEW** | Slot-generation timezone tests |
| `notification_service/channels.py` | `_messages_url` / `_account_url` helpers |
| `notification-service/tests/test_twilio_url.py` | Extended URL tests |
| `mcp-servers/messaging-gateway/pyproject.toml` | Pin `mcp==1.29.0` |
