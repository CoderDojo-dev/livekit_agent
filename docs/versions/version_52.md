# Version 52 — Advisor Registry, Callback Queue Lifecycle & SIP Transfer Rewrite

This branch delivers the **human escalation backbone**: a real advisor registry, a callback queue that keeps promises, and a SIP transfer flow that handles every branch honestly.

## What's new in v52

### Advisor Registry (`routing.Advisor` model)
- PostgreSQL-backed registry of human advisors with skills, availability, and capacity
- Atomic `claim_advisor()` with `FOR UPDATE SKIP LOCKED` — two concurrent escalations never get the same advisor
- Full CRUD + release + on-call lookup via **Business API** (`/api/v1/advisors/*`)
- Seed script with a dev advisor (Chouaib Saad, skills: general/billing/technical/account)

### Callback Queue Lifecycle
- Migration adds `assigned_advisor_id`, `preferred_window` (caller's own words, verbatim), `reason`, `attempts`, `outcome_note`, `completed_at`
- Queue operations: list with overdue detection, stats, claim with SKIP LOCKED, complete (reached / no-answer returns to queue), cancel
- **Business API**: `/api/v1/callbacks/*` with RBAC (conseiller/superviseur/administrateur)

### SIP Transfer Rewrite (`transfer_to_human`)
- Claim advisor → announce → SIP REFER → release on failure → offer callback
- Notifies on-call advisors with full escalation dossier via WhatsApp/email
- Multi-language messages (fr/ar/en)
- Concurrency guard (`human_transfer_in_progress`)

### Supervisor Dashboard
- `CallbackQueue` component with stat tiles, status switcher, overdue filter, inline actions

### Other
- `notify_advisor()` for direct advisor notification
- `RoutingClient` cached via `lru_cache`, registered in `aclose_all_clients()`
- `advisor_callback` notification template
- `BUSINESS_API_URL` setting + docker-compose env var

**Containers:** None new (business-api already existed)
**SDK:** No bump
