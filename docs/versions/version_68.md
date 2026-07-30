# Version 68 — Escalation Consent Gate, Real Callback Queue, STT Keyterms, Payment Deterministic Wording

> **Base branch:** `version_67`
> **Files changed:** 16 modified, 8 new (+573 / -122)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **New env vars:** `CALLBACK_SLOT_MINUTES`, `CALLBACK_DAY_START_HOUR`, `CALLBACK_DAY_END_HOUR`, `CALLBACK_LEAD_MINUTES`, `ALLOW_MOCK_SENSITIVE`

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### 1. Escalation Consent Gate
- `escalate_to_manager` tool now requires `caller_agreed=true`. Premature escalation is deterministically refused — the caller keeps the current persona.
- Immediate escalation (without asking) only for `abuse`, `threat`, `fraud`, `legal` reasons.
- Routing mandate updated: "do NOT escalate straight away" — ask, get consent, then escalate.
- Failed/refused identity check is never a reason to escalate.
- New tests: `tests/transfer/test_escalation_consent.py`.

### 2. Real Callback Queue (Major Rewrite)
- `tasks/callback_schedule_task.py` completely rewritten: offers real slots from the queue, negotiates, and books atomically.
- Fixed spoken sentences per language (fr/ar/en) — never hallucinates an appointment time.
- Idle watchdog (45s) bounds silence, not the entire negotiation.
- Three tools: `accept_slot`, `request_other_time`, `decline_callback`.
- Notification via `notify_first_available` (WhatsApp → email → SMS fallback).

### 3. Callback API (`apps/business-api/`)
- `GET /api/v1/callbacks/slots` — bookable slots derived from advisor registry + existing bookings.
- `POST /api/v1/callbacks/reserve` — atomic slot booking with `pg_advisory_xact_lock`.
- Slot geometry env-driven: `CALLBACK_SLOT_MINUTES` (30), `CALLBACK_DAY_START_HOUR` (8), `CALLBACK_DAY_END_HOUR` (18), `CALLBACK_LEAD_MINUTES` (30).
- Capacity derived from active on-call advisors — never a constant.

### 4. Callback Client (new)
- `clients/callback_client.py` — typed HTTP client to the business API.

### 5. Manager Agent Re-transfer Guard
- `human_transfer_outcome` flag on `SessionUserData`: if a transfer already completed on a previous entry (e.g. callback scheduled), the agent skips re-transfer and reminds the caller.

### 6. SIP Transfer Outcome Tracking
- `human_transfer_outcome` tracks three states: `no_advisor`, `transferred`, `transfer_failed`.

### 7. PaymentConfirmTask Deterministic Wording
- Fixed sentences per language for the amount confirmation question and timeout message.
- Prevents LLM amount drift and language mid-call switching.

### 8. Notification Client Multi-Channel Fallback
- `notify_first_available()` tries WhatsApp → email → SMS, reports which channel carried the message.
- Removed incorrect `"to": customer_id` (UUID being sent as recipient handle).

### 9. STT Keyterms + Safety Fallback
- `config/keyterms.py` — curated list of 24 telecom anglicisms for Deepgram keyterm boosting.
- Same-provider fallback: a plain Deepgram instance without keyterms prevents total STT failure.
- `session_factory.py` auto-injects keyterms if none provided.

### 10. Policy Service Persistence Resilience
- `_persist()` handles `SQLAlchemyError` gracefully: REFUSED/ESCALATE verdicts survive DB failure. AUTHORIZED still fails hard.

### 11. BillingAgent Top-up Clarification
- Explicit instruction: "A recharge or a top-up is NEVER a payment — route to account services."

### New Files Summary

| File | Purpose |
|------|---------|
| `src/clients/callback_client.py` | Typed HTTP client for callback queue API |
| `src/config/keyterms.py` | Curated telecom anglicisms for Deepgram STT |
| `tests/keyterms/test_keyterms.py` | Keyterm list stability tests |
| `tests/resilience/test_task_language.py` | Task language resolution tests |
| `tests/transfer/test_escalation_consent.py` | Escalation consent gate tests |
| `tests/transfer/test_transfer_is_terminal.py` | Transfer terminal behavior tests |
