# Version 70 — Notification Multi-Channel, Twilio Credential Probe, SIP Transfer Toggle

> **Base branch:** `version_69`
> **Files changed:** 8 modified (+130 / -16)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **New env vars:** `SIP_TRANSFER_ENABLED` (default `false`)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### 1. Multi-Channel Notification (`notification_client.py`)
- New `notify_all_available()` method sends the same confirmation on every reachable channel (WhatsApp, email) in parallel, then falls back to SMS if all primaries fail.
- Returns a list of all channels that actually delivered, so the agent can say "Vous recevez la confirmation par WhatsApp et e-mail."
- `callback_schedule_task.py` updated to use `notify_all_available()` instead of `notify_first_available()`. Spoken confirmation now lists every channel that went out.

### 2. Twilio Channel Fixes (`channels.py`)
- `_sid` and `_token` use `os.getenv()` instead of `os.environ[]` (prevents KeyError on missing vars).
- `configured` property now also checks `self._token` (not just `_sid` and `_from`).
- `_address()` static method strips a doubled `whatsapp:` prefix before re-adding it, preventing Twilio from receiving `whatsapp:whatsapp:+216...`.
- `verify_credentials()` (new) — actually probes Twilio REST API and SMTP to confirm credentials work, not just whether env vars are set.
- SMTP `timeout=10` to prevent hangs on unreachable hosts.
- SMTP `_host` uses `os.getenv()` instead of `os.environ[]`.

### 3. SIP Transfer Toggle (`sip_transfer.py`)
- New env var `SIP_TRANSFER_ENABLED` (default `false`). When disabled, `transfer_to_human` skips the SIP REFER entirely and goes straight to a callback offer.
- `human_transfer_outcome` set to `callback_only`.
- Test updated to set `SIP_TRANSFER_ENABLED=true`.

### 4. Credential Health Endpoint (`main.py`)
- `GET /health/credentials` — live credential probe (slow, never call from readiness probe).

### 5. Service Layer Fix (`service.py`)
- Removed `status == "sent"` guard on DB persistence: all notify attempts (sent or failed) are now persisted for audit.

### Files Changed (8 modified)

| File | Summary |
|------|---------|
| `clients/notification_client.py` | `notify_all_available()` multi-channel delivery |
| `tasks/callback_schedule_task.py` | Uses `notify_all_available()`, `_JOIN` for channel list |
| `telephony/sip_transfer.py` | `SIP_TRANSFER_ENABLED` gate, early callback path |
| `tests/transfer/test_transfer_is_terminal.py` | Sets `SIP_TRANSFER_ENABLED=true` in test |
| `notification_service/channels.py` | `os.getenv`, `_address()` prefix guard, `verify_credentials()` |
| `notification_service/main.py` | `/health/credentials` endpoint |
| `notification_service/service.py` | Removed `sent` guard on persist |
| `tests/test_twilio_url.py` | `test_whatsapp_prefix_is_not_doubled` |
