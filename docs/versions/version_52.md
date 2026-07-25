# Version 52 — Advisor Registry, Callback Queue Lifecycle & SIP Transfer Rewrite

> **Base branch:** `version_51`
> **Commit range:** version_51..version_52
> **Files changed:** 22 (+1207 / -43)

---

## Containers & SDK

| Item                | Change                                      |
|---------------------|---------------------------------------------|
| New containers      | None (`business-api` already existed)        |
| livekit-agents SDK  | No bump                                     |

---

## What's New

### 1. Advisor Registry (routing schema)

A real, queryable registry of human advisors that the voice agent escalates to. This replaces
the previous approach where transfer destinations were implicit or hardcoded.

- **New `routing.Advisor` model** — UUID PK, `full_name`, `email`, `phone_e164`, `sip_uri`,
  `skills` (comma-separated tags matched against the escalating persona), `language`,
  `status` (`available` / `busy` / `offline`), `max_concurrent_calls`, `active_calls`,
  `is_on_call`, `is_active`.
- **Migration `0012_routing_advisors`** — creates the `routing` schema + `advisors` table with
  `CheckConstraint`s on status vocabulary, positive capacity, and non-negative active calls.
- **Atomic `claim_advisor()`** — uses `FOR UPDATE SKIP LOCKED` so two simultaneous escalations
  are never handed the same advisor; capacity is re-checked inside the lock.
- **`release_advisor()`** — frees a claimed advisor when the transfer fails or the call ends.
- **Full CRUD** — `list_advisors()`, `create_advisor()`, `update_advisor()`, `delete_advisor()`.
- **`on_call_advisors()`** — advisors who receive the dossier when a callback is scheduled.
- **Seed script** (`seed_advisors.py`) — idempotent dev advisor (Chouaib Saad, +21626078277,
  skills: general / billing / technical / account).

### 2. Callback Queue Lifecycle

A scheduled callback was previously written with `status='pending'` and never read again. This
gives the row a full life: it can be listed, claimed by exactly one advisor, completed with an
outcome, retried, or cancelled — and a supervisor can see which ones are overdue.

- **Migration `0013_callback_lifecycle`** — adds to `conversation.callback_schedules`:
  - `assigned_advisor_id` (FK → `routing.advisors`, `ON DELETE SET NULL`)
  - `preferred_window` (the caller's own words, e.g. "demain matin", kept verbatim)
  - `reason` (why the callback was needed)
  - `attempts` (how many times an advisor tried)
  - `outcome_note` (free-text result)
  - `completed_at`
  - Composite index on `(status, scheduled_time)` for queue queries.
- **Lifecycle operations** (`callbacks.py`):
  - `list_callbacks()` — soonest + highest-priority first, with `overdue` flag.
  - `queue_stats()` — pending / overdue / completed counts for the dashboard.
  - `claim_next()` — `FOR UPDATE SKIP LOCKED` so concurrent advisors get different callers.
  - `complete_callback(reached=True/False)` — `reached=False` returns it to the queue.
  - `cancel_callback()` — supervisor action.
- **Hydration** — each row is enriched with customer name/phone and advisor name in one query.

### 3. Business API Endpoints

- **Advisor registry:** `GET /api/v1/advisors`, `POST /api/v1/advisors`,
  `PATCH /api/v1/advisors/{id}`, `DELETE /api/v1/advisors/{id}`,
  `POST /api/v1/advisors/claim`, `POST /api/v1/advisors/{id}/release`,
  `GET /api/v1/advisors/on-call`.
- **Callback queue:** `GET /api/v1/callbacks`, `GET /api/v1/callbacks/stats`,
  `POST /api/v1/callbacks/claim`, `POST /api/v1/callbacks/{id}/complete`,
  `POST /api/v1/callbacks/{id}/cancel`.
- **RBAC** enforced per spec section 17 (`conseiller` / `superviseur` / `administrateur`).

### 4. Routing Client (agent-worker)

- **`RoutingClient`** — claims and releases advisors via the business API; resolves an
  `AdvisorDestination` dataclass with a `transfer_uri` property (`sip:` URI when configured,
  otherwise `tel:` number).
- Cached via `lru_cache` and registered in `aclose_all_clients()` for pool cleanup.

### 5. SIP Transfer Rewrite (`transfer_to_human`)

The full escalation flow, every branch producing honest speech:

| Scenario                           | Behaviour                                             |
|------------------------------------|-------------------------------------------------------|
| Advisor claimed + transfer succeeds | Call moves to the advisor (cold SIP REFER transfer)  |
| Advisor claimed + transfer fails    | Advisor released, caller told plainly, callback offered |
| No advisor available                 | Caller told plainly, callback offered                |
| Callback scheduled                   | On-call advisor notified WITH the dossier            |

- **`_find_sip_caller_identity()`** — locates the caller's SIP participant in the room
  (required by `TransferSIPParticipant`; returns `None` outside telephony).
- **`_notify_on_call_advisors()`** — sends the escalation dossier to every on-call advisor
  via WhatsApp (primary) and email, returning how many were reached.
- **`_offer_callback()`** — schedules a callback and notifies advisors; the outcome message
  tells the agent whether a human was actually notified.
- **Multi-language messages** (fr/ar/en) for transfer announcements and no-advisor states.
- **Concurrent-transfer guard** — `human_transfer_in_progress` flag prevents double-escalation.

### 6. Notification Client Enhancement

- **`notify_advisor()`** — sends a message directly to an advisor via an explicit `to` handle,
  bypassing customer-id resolution (advisors are not customers). Returns `bool` sent-status.

### 7. Callback Schedule Task

- Records `preferred_window` (caller's own words, verbatim) and `reason` into the DB.
- Sends a written confirmation via the notification-service.

### 8. Supervisor Dashboard

- **New `CallbackQueue` component** with:
  - Stat tiles: pending / overdue (red when > 0) / completed.
  - Status switcher (Pending / Completed / Cancelled).
  - Overdue-only filter toggle.
  - Inline row actions: outcome note input + Reached / No answer / Cancel buttons.
- New `Callback` + `CallbackStats` TypeScript types.
- New API methods: `callbacks()`, `callbackStats()`, `completeCallback()`, `cancelCallback()`.
- Integrated into the sidebar navigation as "Callback Queue".
- SCSS styles for the callback stats grid and action layout.

### 9. Other

- **`advisor_callback` notification template** (fr/ar/en) for on-call advisor notifications.
- **`BUSINESS_API_URL`** setting added to agent-worker config.
- **Docker Compose** — `BUSINESS_API_URL` env var added to the `agent-worker` container.

---

## Files Added

| File | Description |
|------|-------------|
| `packages/persistence/src/persistence/models/routing.py` | `Advisor` ORM model |
| `packages/persistence/alembic/versions/0012_routing_advisors.py` | Advisor table migration |
| `packages/persistence/alembic/versions/0013_callback_lifecycle.py` | Callback lifecycle migration |
| `packages/persistence/seed/seed_advisors.py` | Dev advisor seed script |
| `apps/business-api/src/business_api/advisors.py` | Advisor registry operations |
| `apps/business-api/src/business_api/callbacks.py` | Callback queue operations |
| `apps/supervisor-dashboard/src/components/CallbackQueue.tsx` | Callback queue UI |
