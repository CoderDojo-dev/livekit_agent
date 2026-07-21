# version_46 — Notification-Service Live-Only + Centralized Contact Resolution

## What Changed

### Notification Service: Live-Only Rewrite
The notification-service is now **live-only** — all mock channels removed:

- **`MockSmsChannel`, `MockWhatsAppChannel`, `MockEmailChannel`** deleted
- **`CONNECTOR_MODE` env var** removed from notification-service
- **`ChannelUnavailable` exception** — raised when a channel is unconfigured or the provider rejects the send. No silent mock fallback.
- **`get_channel()`** raises `ChannelUnavailable` instead of returning a mock

### WhatsApp Now the Primary Channel
- Default channel changed from `sms` to **`whatsapp`** in `NotifyRequest`
- `ticket_created` notification now sends on **whatsapp** (not sms)
- Twilio WhatsApp sandbox default number (`+14155238886`) set in `.env.example`
- SMS stays supported in code but is no longer the default

### Centralized Contact Resolution (`contacts.py`)
New module `services/notification-service/src/notification_service/contacts.py`:

- **`resolve_recipient(customer_id, channel)`** — maps customer_id → (handle, language) from `crm.customers`
  - `whatsapp` / `sms` → `customer.contact_number`
  - `email` → `customer.email`
  - Language falls back to `customer.preferred_language`
- **`ContactUnavailable`** exception — raised when DB is not configured, customer is unknown, or customer has no handle for that channel. No UUID-addressing or fake sends.
- **Why centralize**: callers (ticketing, billing) only pass a `customer_id` — never a phone or email. Contact details live in exactly one place, every caller is decoupled from PII.

### Honest Failure Propagation (`service.py`)
- `notify()` catches `ChannelUnavailable` and any other exception → returns **`sent=False`** with the actual `reason`
- `NotifyResponse` gains a `reason` field (empty on success, descriptive on failure)
- DB record written with `status='failed'` on failure (previously only `'sent'`)
- Language auto-resolves from customer's `preferred_language` when caller does not force one

### New Templates
- **`ticket_resolved`** — "Votre ticket {ticket_id} a été résolu." (fr/ar/en)
- **`ticket_updated`** — "Votre ticket {ticket_id} a été mis à jour." (fr/ar/en)

### Health Endpoint
- `/health` now reports per-channel configuration status:
  ```json
  {"status": "ok", "sms": {"label": "SMS (Twilio)", "configured": false, "name": "sms"}, ...}
  ```

### SDK / Dependency Changes
- **`httpx==0.28.1`** added to `pyproject.toml` (needed by contacts.py for potential future HTTP contact resolution)

## GLPI Ticketing
- `create_ticket` notification call changed: passes `customer_id` only (no `to`), uses `whatsapp` channel — the notification-service resolves the contact handle itself

## Infra / Config Cleanup
- **`docker-compose.apps.yml`**: removed leftover `CONNECTOR_MODE`, `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` env vars from ticketing-glpi service (already removed from code in v44)
- **GLPI `/health`**: now reports `glpi=configured|unconfigured` instead of `connector_mode=live|mock`
- **`.env.example`**: WhatsApp default number set; GLPI endpoint now has commented-out old endpoint; comments updated for live-only semantics

## Pilot Seed Data
- **`seed_pilot.py`**: real email + contact_number for all 3 pilot customers (Amine → `choiyebsaad2000@gmail.com`, Yousra → `chouaibsaad.contact@gmail.com`, Karim → `ws0461646@gmail.com`; all use `+21626078277` for WhatsApp)
- **`sync_pilot_contacts.py`** (new): in-place update script for existing databases — updates phone/email by `national_id` without wiping or re-seeding

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `services/notification-service/src/notification_service/channels.py` | MODIFIED | Removed all mock channels; ChannelUnavailable; channel_status() |
| `services/notification-service/src/notification_service/contacts.py` | NEW | Centralized customer_id → handle + language resolution |
| `services/notification-service/src/notification_service/service.py` | MODIFIED | Live-only send; sent=False with reason on failure; language auto-resolve |
| `services/notification-service/src/notification_service/schemas.py` | MODIFIED | Default channel=whatsapp; reason field; language auto-resolve |
| `services/notification-service/src/notification_service/templates.py` | MODIFIED | Added ticket_resolved, ticket_updated templates |
| `services/notification-service/src/notification_service/main.py` | MODIFIED | /health with per-channel status |
| `services/notification-service/pyproject.toml` | MODIFIED | Added httpx dependency |
| `.env.example` | MODIFIED | WhatsApp default, live-only comments |
| `infra/docker-compose/docker-compose.apps.yml` | MODIFIED | Removed GLPI/CONNECTOR_MODE leftovers |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/server.py` | MODIFIED | /health reports glpi=configured/unconfigured |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` | MODIFIED | whatsapp channel + centralized customer_id |
| `packages/persistence/seed/seed_pilot.py` | MODIFIED | Real email/contact_number for pilot customers |
| `packages/persistence/seed/sync_pilot_contacts.py` | NEW | In-place contact update script |
