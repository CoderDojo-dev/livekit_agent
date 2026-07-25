# Version 46 — Notification-service Live-only & Centralized Contact Resolution

## What's new
- **All mock channels removed**: MockSmsChannel, MockWhatsAppChannel, MockEmailChannel, CONNECTOR_MODE deleted
- **WhatsApp is PRIMARY channel** (default); ticket_created now sends on WhatsApp, not SMS
- **`ChannelUnavailable` exception**: unconfigured/failed channels return `sent=False` with reason
- **`contacts.py`**: centralized `customer_id → (handle, language)` resolution from `crm.customers`; raises `ContactUnavailable` when DB, customer, or handle is missing
- **`NotifyResponse` gains `reason` field**; `notify()` returns `sent=False` with reason on any failure
- **New templates**: `ticket_resolved`, `ticket_updated` (fr/ar/en)
- **`/health` endpoint** reports per-channel configuration status
- **GLPI ticketing**: ticket_created notification uses WhatsApp + centralized `customer_id`
- **Seed data**: `seed_pilot.py` with real email/contact_number for 3 pilot customers; `sync_pilot_contacts.py` script
