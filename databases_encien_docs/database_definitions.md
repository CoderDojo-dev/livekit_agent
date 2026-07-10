# Database Definitions — Telecom AI Voice Agent Platform

## Overview

- **RDBMS:** PostgreSQL 16 (Alpine)
- **URL:** `postgresql+psycopg://telecom:telecom@localhost:5432/telecom`
- **ORM:** SQLAlchemy 2.x (declarative)
- **Migrations:** Alembic (8 migration files, linear chain)
- **Schemas:** 12 bounded-context schemas
- **Tables:** 27 tables + 1 live view + 6 GIN indexes

### Global Conventions (from `persistence/base.py`)

Every table inherits from these mixins:

| Mixin | Fields | Description |
|-------|--------|-------------|
| `UUIDPrimaryKey` | `id UUID PK DEFAULT uuid_generate_v4()` | All tables use UUID v4 primary keys |
| `Timestamps` | `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` | Both have `server_default=now()`, `updated_at` has a `BEFORE UPDATE` trigger |
| `SoftDelete` | `deleted_at TIMESTAMPTZ NULL` | For master/reference data only; operational logs are append-only |

Other conventions:
- Money stored as `NUMERIC(12,2)` — never float
- Constraint/index names follow a deterministic naming convention
- All timestamps are UTC with timezone

### Triggers

The `set_updated_at()` PL/pgSQL function is created in migration `0001`. It is attached as a `BEFORE UPDATE` trigger on tables that have mutable `updated_at`:

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
```

Trigger registrations by trigger and migration:

| Migration | Table(s) with `trg_<table>_updated` trigger |
|-----------|----------------------------------------------|
| 0001 | `crm.customers`, `crm.subscriptions`, `billing.accounts`, `billing.invoices`, `ocs.balance_accounts` |
| 0002 | `execution.action_ledger` |
| 0003 | `conversation.callback_schedules` |
| 0004 | `billing.payments`, `billing.payment_plans`, `sim.block_unblock_cases` |
| 0006 | `reference.business_rules` |
| 0007 | `oss.network_elements`, `oss.outages`, `provisioning.provisioning_requests`, `provisioning.sim_orders` |

---

## Schema: `crm` — Customer Relationship Management

Tables: `customers`, `subscriptions`, `consent_records`, `customer_interactions`

### crm.customers

Single source of truth for customer identity.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, `uuid_generate_v4()` | Primary key |
| `national_id` | VARCHAR(50) | NOT NULL, UNIQUE | CIN (National ID card number) |
| `first_name` | VARCHAR(100) | NOT NULL | Customer first name |
| `last_name` | VARCHAR(100) | NOT NULL | Customer last name |
| `email` | VARCHAR(255) | UNIQUE, NULLABLE | Email address |
| `contact_number` | VARCHAR(20) | NULL | Contact phone number |
| `preferred_language` | VARCHAR(10) | NOT NULL, DEFAULT 'fr', CHECK IN ('fr','ar','en') | Language preference |
| `segment` | VARCHAR(80) | INDEX, NULL | Customer segment (e.g. residential, business) |
| `vip_flag` | BOOLEAN | NOT NULL, DEFAULT false | VIP customer flag |
| `fraud_suspected` | BOOLEAN | NOT NULL, DEFAULT false | Fraud suspicion flag |
| `address` | TEXT | NULL | Street address |
| `city` | VARCHAR(100) | NULL | City |
| `region` | VARCHAR(100) | NULL | Region/governorate |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', INDEX, CHECK IN ('active','suspended','closed') | Account status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |

**Relationships:** `subscriptions` (one-to-many)

### crm.subscriptions

Owns the MSISDN as a UNIQUE attribute (never a join key).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id ON DELETE RESTRICT, INDEX | Owning customer |
| `msisdn` | VARCHAR(20) | NOT NULL, UNIQUE | Phone number (FN, not an FK) |
| `plan_type` | VARCHAR(20) | NOT NULL, CHECK IN ('PREPAID','POSTPAID') | Billing plan type |
| `plan_code` | VARCHAR(50) | NULL | Plan code (ref → reference.products) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'ACTIVE', CHECK IN ('ACTIVE','SUSPENDED','BLOCKED','TERMINATED') | Subscription status |
| `roaming_enabled` | BOOLEAN | NOT NULL, DEFAULT FALSE | International roaming flag |
| `activation_date` | DATE | NULL | Activation date |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |

**Relationships:** `customer` (many-to-one)

### crm.consent_records

Recording consent and data-processing consent audit.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NULL, FK → crm.customers.id | Identified customer (NULL for unknown callers) |
| `session_id` | UUID | NOT NULL, INDEX | Agent session ID |
| `consent_type` | VARCHAR(40) | NOT NULL, DEFAULT 'call_recording', CHECK IN ('call_recording','data_processing','marketing') | Type of consent |
| `granted` | BOOLEAN | NOT NULL | True = consented, false = denied |
| `language` | VARCHAR(10) | NULL, CHECK IN ('fr','ar','en') | Language used during consent capture |
| `captured_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Timestamp of consent capture |

### crm.customer_interactions

Log of every customer interaction across channels.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id, INDEX | Identified customer |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id | Subscription context |
| `session_id` | UUID | NULL, INDEX | Agent session ID |
| `channel` | VARCHAR(20) | NOT NULL, DEFAULT 'voice', CHECK IN ('voice','chat','sms','email','whatsapp') | Interaction channel |
| `detected_intent` | VARCHAR(80) | NULL | Intent detected by the agent |
| `resolution` | TEXT | NULL | Resolution summary |
| `summary` | TEXT | NULL | Full interaction summary |
| `language` | VARCHAR(10) | NULL, CHECK IN ('fr','ar','en') | Interaction language |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `billing` — Billing Domain

Tables: `accounts`, `invoices`, `invoice_items`, `payments`, `payment_plans`, `notifications`

### billing.accounts

Postpaid billing accounts (prepaid goes via OCS).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id, INDEX | Owning customer |
| `account_number` | VARCHAR(40) | NOT NULL, UNIQUE | Billing account number |
| `account_type` | VARCHAR(20) | NOT NULL, DEFAULT 'postpaid', CHECK IN ('postpaid','hybrid') | Account type |
| `billing_cycle_day` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 28 | Day of month cycle closes |
| `payment_terms_days` | INTEGER | NOT NULL, DEFAULT 15 | Days until payment due |
| `currency_code` | VARCHAR(3) | NOT NULL, DEFAULT 'TND' | Currency (TND) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK IN ('active','dunning','suspended','closed') | Account status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |

**Relationships:** `customer`, `invoices` (one-to-many)

### billing.invoices

Postpaid invoices.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `account_id` | UUID | NOT NULL, FK → billing.accounts.id, INDEX | Billing account |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id, INDEX | Customer |
| `invoice_number` | VARCHAR(40) | NOT NULL, UNIQUE | Invoice reference |
| `period_start` | DATE | NOT NULL | Billing period start |
| `period_end` | DATE | NOT NULL | Billing period end |
| `issue_date` | DATE | NOT NULL | Invoice issue date |
| `due_date` | DATE | NOT NULL | Payment due date |
| `subtotal` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Subtotal before tax |
| `tax_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Tax amount |
| `total_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Total amount |
| `outstanding_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Unpaid balance |
| `currency_code` | VARCHAR(3) | NOT NULL, DEFAULT 'TND' | Currency |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'issued', INDEX, CHECK IN ('draft','issued','paid','partial','overdue','disputed','void') | Invoice status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

**Relationships:** `account`, `customer`, `items` (one-to-many with cascade delete)

### billing.invoice_items

Individual line items on an invoice.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `invoice_id` | UUID | NOT NULL, FK → billing.invoices.id ON DELETE CASCADE, INDEX | Parent invoice |
| `description` | VARCHAR(255) | NOT NULL | Line item description |
| `charge_type` | VARCHAR(50) | NOT NULL | Type of charge |
| `quantity` | NUMERIC(12,4) | NOT NULL, DEFAULT 1 | Quantity |
| `unit_price` | NUMERIC(12,4) | NOT NULL, DEFAULT 0 | Unit price |
| `amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Total amount |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

**Relationships:** `invoice` (many-to-one)

### billing.payments

Captured payments with idempotency support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `account_id` | UUID | NOT NULL, FK → billing.accounts.id, INDEX | Billing account |
| `invoice_id` | UUID | NULL, FK → billing.invoices.id, INDEX | Paid invoice |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id | Customer |
| `amount` | NUMERIC(12,2) | NOT NULL | Payment amount |
| `currency_code` | VARCHAR(3) | NOT NULL, DEFAULT 'TND' | Currency |
| `method` | VARCHAR(30) | NOT NULL, CHECK IN ('card','bank_transfer','wallet','voucher','cash') | Payment method |
| `gateway_reference` | VARCHAR(120) | NULL | Payment gateway reference |
| `idempotency_key` | VARCHAR(80) | UNIQUE, NULL | Idempotency key (mirrors execution.action_ledger) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','succeeded','failed','refunded') | Payment status |
| `paid_at` | TIMESTAMPTZ | NULL | Actual payment timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### billing.payment_plans

Deferral/installment plans for payment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `account_id` | UUID | NOT NULL, FK → billing.accounts.id | Billing account |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id | Customer |
| `total_amount` | NUMERIC(12,2) | NOT NULL | Total plan amount |
| `installment_count` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 12 | Number of installments |
| `installment_amount` | NUMERIC(12,2) | NOT NULL | Per-installment amount |
| `deferral_until` | DATE | NULL | Deferral end date (if deferred start) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK IN ('proposed','active','completed','defaulted','cancelled') | Plan status |
| `policy_verdict_id` | UUID | NULL | Loose ref → policy.policy_verdicts |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### billing.notifications

Outbound customer notification log (reminders, alerts, confirmations).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NULL, FK → crm.customers.id, INDEX | Target customer |
| `channel` | VARCHAR(20) | NOT NULL, CHECK IN ('sms','whatsapp','email') | Notification channel |
| `template_code` | VARCHAR(80) | NULL | Notification template |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'sent', CHECK IN ('queued','sent','failed') | Delivery status |
| `sent_at` | TIMESTAMPTZ | NULL, DEFAULT now() | Sent timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `ocs` — Online Charging System (Prepaid)

Tables: `balance_accounts`, `recharges`

### ocs.balance_accounts

Per-subscription, per-balance-type prepaid balances.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `subscription_id` | UUID | NOT NULL, FK → crm.subscriptions.id, INDEX | Prepaid subscription |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id | Customer |
| `balance_type` | VARCHAR(20) | NOT NULL, CHECK IN ('main','data','voice','sms') | Balance type |
| `balance_value` | NUMERIC(14,4) | NOT NULL, DEFAULT 0 | Current balance |
| `balance_unit` | VARCHAR(10) | NOT NULL, CHECK IN ('TND','GB','MB','MIN','SMS') | Unit of measure |
| `expiry_date` | DATE | NULL | Balance expiry date |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK IN ('active','expired','suspended') | Balance status |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

**Unique constraint:** `(subscription_id, balance_type)` — one balance per type per subscription.

**Relationships:** `subscription`, `customer`

### ocs.recharges

Prepaid top-up records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `subscription_id` | UUID | NOT NULL, FK → crm.subscriptions.id, INDEX | Subscription |
| `customer_id` | UUID | NOT NULL, FK → crm.customers.id | Customer |
| `recharge_code` | VARCHAR(50) | NULL | Scratch card / recharge code |
| `amount` | NUMERIC(12,2) | NOT NULL | Recharge amount |
| `bonus_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Bonus / promotional amount |
| `channel` | VARCHAR(20) | NOT NULL, CHECK IN ('app','web','ussd','scratch_card','agent') | Recharge channel |
| `idempotency_key` | VARCHAR(80) | UNIQUE, NULL | Idempotency key (mirrors execution.action_ledger) |
| `transaction_reference` | VARCHAR(120) | NULL | External transaction ref |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','completed','failed') | Recharge status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `sim` — SIM Lifecycle

Table: `block_unblock_cases`

### sim.block_unblock_cases

Identity-gated SIM block/unblock/reactivate operations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `subscription_id` | UUID | NOT NULL, FK → crm.subscriptions.id, INDEX | Subscription |
| `action` | VARCHAR(20) | NOT NULL, CHECK IN ('BLOCK','UNBLOCK','UNLOCK_PUK','REACTIVATE') | SIM action type |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','identity_verified','completed','escalated','rejected') | Case status |
| `identity_verified` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether identity was verified |
| `policy_verdict_id` | UUID | NULL | Loose ref → policy.policy_verdicts |
| `idempotency_key` | VARCHAR(80) | UNIQUE, NULL | Idempotency key |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

---

## Schema: `oss` — Operations Support System (Network)

Tables: `network_elements`, `alarms`, `outages`

### oss.network_elements

Network infrastructure inventory.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `element_type` | VARCHAR(40) | NOT NULL, CHECK IN ('cell_site','bts','router','switch','olt','core') | Type of network element |
| `vendor` | VARCHAR(60) | NULL | Vendor name |
| `model` | VARCHAR(80) | NULL | Hardware model |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK IN ('active','degraded','down','maintenance') | Element status |
| `region` | VARCHAR(80) | INDEX, NULL | Geographic region |
| `ip_address` | VARCHAR(45) | NULL | Management IP address |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### oss.alarms

Network alarms/events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `network_element_id` | UUID | NULL, FK → oss.network_elements.id, INDEX | Associated network element |
| `severity` | VARCHAR(20) | NOT NULL, CHECK IN ('critical','major','minor','warning') | Alarm severity |
| `alarm_type` | VARCHAR(60) | NULL | Alarm type/code |
| `description` | TEXT | NULL | Alarm description |
| `acknowledged_at` | TIMESTAMPTZ | NULL | Acknowledged timestamp |
| `cleared_at` | TIMESTAMPTZ | NULL | Cleared timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### oss.outages

Known service outages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `region` | VARCHAR(80) | INDEX, NULL | Affected region |
| `area` | VARCHAR(120) | NULL | Specific area |
| `affected_services` | VARCHAR(120) | NULL | e.g. "mobile,data" |
| `severity` | VARCHAR(20) | NOT NULL, DEFAULT 'minor', CHECK IN ('critical','major','minor') | Outage severity |
| `start_time` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Outage start time |
| `end_time` | TIMESTAMPTZ | NULL | Outage end time |
| `resolved` | BOOLEAN | NOT NULL, DEFAULT FALSE | Resolution flag |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

---

## Schema: `provisioning` — Provisioning & Ordering

Tables: `provisioning_requests`, `sim_orders`, `plan_change_history`

### provisioning.provisioning_requests

Provisioning action requests (change plan, activate roaming, etc.).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id, INDEX | Target subscription |
| `customer_id` | UUID | NULL, FK → crm.customers.id | Customer |
| `action_type` | VARCHAR(60) | NOT NULL | e.g. CHANGE_PLAN, ACTIVATE_ROAMING |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','in_progress','completed','failed') | Request status |
| `idempotency_key` | VARCHAR(80) | UNIQUE, NULL | Idempotency key |
| `policy_verdict_id` | UUID | NULL | FK → policy.policy_verdicts |
| `parameters` | JSONB | NOT NULL, DEFAULT '{}' | Action parameters (GIN indexed) |
| `requested_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Request timestamp |
| `completed_at` | TIMESTAMPTZ | NULL | Completion timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### provisioning.sim_orders

SIM card/eSIM orders.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NULL, FK → crm.customers.id, INDEX | Customer |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id | Subscription |
| `sim_type` | VARCHAR(20) | NOT NULL, DEFAULT 'physical', CHECK IN ('physical','esim') | SIM type |
| `iccid` | VARCHAR(22) | NULL | ICCID of the SIM |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'requested', CHECK IN ('requested','shipped','activated','cancelled') | Order status |
| `tracking_code` | VARCHAR(60) | NULL | Shipping tracking code |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### provisioning.plan_change_history

Audit trail of plan changes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id, INDEX | Subscription |
| `from_plan` | VARCHAR(60) | NULL | Previous plan code |
| `to_plan` | VARCHAR(60) | NOT NULL | New plan code |
| `changed_by` | VARCHAR(20) | NOT NULL, DEFAULT 'agent', CHECK IN ('agent','self_service','advisor') | Change initiator |
| `effective_date` | DATE | NULL | Effective change date |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `ticketing` — Ticketing (GLPI Mirror)

Tables: `tickets`

### ticketing.tickets

Local cache of GLPI tickets (GLPI remains source of truth).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `glpi_ticket_id` | VARCHAR(40) | NOT NULL, UNIQUE | GLPI ticket ID |
| `customer_id` | UUID | NULL, FK → crm.customers.id, INDEX | Customer |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id | Subscription |
| `category` | VARCHAR(40) | NOT NULL, DEFAULT 'other', CHECK IN ('network_complaint','formal_complaint','technical','billing','other') | Ticket category |
| `subject` | VARCHAR(255) | NULL | Ticket subject |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'open', CHECK IN ('open','in_progress','pending','resolved','closed') | Ticket status |
| `priority` | VARCHAR(10) | NULL, CHECK IN ('low','medium','high','urgent') | Priority |
| `last_synced_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last sync with GLPI |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `conversation` — Call Sessions & Agent Runtime

Tables: `call_sessions`, `turns`, `sentiment_samples`, `escalation_cases`, `callback_schedules`

### conversation.call_sessions

Durable record of every call session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `customer_id` | UUID | NULL, FK → crm.customers.id, INDEX | Identified customer |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id | Subscription |
| `msisdn` | VARCHAR(20) | NULL | Raw caller ID (pre-resolution) |
| `channel` | VARCHAR(20) | NOT NULL, DEFAULT 'voice', CHECK IN ('voice','chat') | Communication channel |
| `livekit_room` | VARCHAR(120) | NULL | LiveKit room name |
| `start_time` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Call start time |
| `end_time` | TIMESTAMPTZ | NULL | Call end time |
| `duration_seconds` | INTEGER | NULL | Call duration |
| `final_disposition` | VARCHAR(20) | NULL, CHECK IN ('resolved','escalated','dropped','abandoned') | Call outcome |
| `max_frustration_score` | NUMERIC(5,2) | NOT NULL, DEFAULT 0 | Peak frustration during call |
| `recording_consent` | BOOLEAN | NULL | Recording consent given by caller |
| `audio_record_url` | TEXT | NULL | URL to audio recording |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### conversation.turns

Per-turn transcript records (PII-masked).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NOT NULL, FK → conversation.call_sessions.id, INDEX | Parent session |
| `turn_index` | INTEGER | NOT NULL | Sequential turn number |
| `speaker` | VARCHAR(10) | NOT NULL, CHECK IN ('caller','agent') | Speaker role |
| `active_agent` | VARCHAR(40) | NULL | Active agent persona name |
| `detected_language` | VARCHAR(10) | NULL, CHECK IN ('fr','ar','en') | Detected language |
| `transcript_masked` | TEXT | NULL | PII-masked transcript |
| `detected_intent` | VARCHAR(80) | NULL | Detected caller intent |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

**Unique constraint:** `(session_id, turn_index, speaker)`

### conversation.sentiment_samples

Per-turn sentiment scores.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NOT NULL, FK → conversation.call_sessions.id, INDEX | Parent session |
| `turn_index` | INTEGER | NOT NULL | Corresponding turn index |
| `score` | NUMERIC(5,2) | NOT NULL | Sentiment score (-1 to 1) |
| `label` | VARCHAR(20) | NULL, CHECK IN ('positive','neutral','negative','angry') | Sentiment label |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### conversation.escalation_cases

Escalation events (to manager or human advisor).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NOT NULL, FK → conversation.call_sessions.id | Parent session |
| `customer_id` | UUID | NULL, FK → crm.customers.id | Customer |
| `trigger` | VARCHAR(40) | NOT NULL | Escalation trigger reason |
| `target` | VARCHAR(20) | NOT NULL, CHECK IN ('manager_agent','human_advisor') | Escalation target |
| `dossier` | JSONB | NOT NULL | Escalation context data (GIN indexed) |
| `resolution` | VARCHAR(20) | NULL, CHECK IN ('transferred','queued','callback_scheduled','resolved') | Resolution status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### conversation.callback_schedules

Scheduled callbacks.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NULL, FK → conversation.call_sessions.id | Source session |
| `customer_id` | UUID | NULL, FK → crm.customers.id | Customer |
| `subscription_id` | UUID | NULL, FK → crm.subscriptions.id | Subscription |
| `scheduled_time` | TIMESTAMPTZ | NOT NULL | When to call back |
| `priority_level` | INTEGER | NOT NULL, DEFAULT 1 | Callback priority |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','completed','cancelled') | Callback status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

---

## Schema: `policy` — Policy Engine

Tables: `policy_verdicts`

### policy.policy_verdicts

Every authorize/refuse/escalate decision, append-only.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NOT NULL, INDEX | Agent session ID |
| `customer_id` | UUID | NULL | Customer |
| `requested_action` | VARCHAR(80) | NOT NULL, INDEX | Action being evaluated |
| `direction` | VARCHAR(10) | NOT NULL, DEFAULT 'inbound', CHECK IN ('inbound','outbound') | API call direction |
| `verdict` | VARCHAR(12) | NOT NULL, CHECK IN ('AUTHORIZED','REFUSED','ESCALATE') | Policy decision |
| `rule_id` | VARCHAR(80) | NOT NULL | Rule that produced this verdict |
| `justification` | TEXT | NOT NULL | Human-readable justification |
| `inputs_snapshot` | JSONB | NOT NULL | Input parameters at evaluation time (GIN indexed) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `execution` — Action Execution

Tables: `action_ledger`

### execution.action_ledger

Idempotent action ledger — every action runs at most once.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `session_id` | UUID | NOT NULL, INDEX | Agent session |
| `customer_id` | UUID | NULL | Customer |
| `subscription_id` | UUID | NULL | Subscription |
| `action_type` | VARCHAR(80) | NOT NULL | Action type (e.g. PAYMENT, CHANGE_PLAN) |
| `target_domain` | VARCHAR(20) | NOT NULL | Target domain (e.g. billing, ocs) |
| `idempotency_key` | VARCHAR(80) | NOT NULL, UNIQUE | Idempotency guarantee |
| `policy_verdict_id` | UUID | NOT NULL, FK → policy.policy_verdicts.id | Authorizing verdict |
| `parameters` | JSONB | NOT NULL | Action parameters (GIN indexed) |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending','succeeded','failed','retrying') | Execution status |
| `attempt_count` | INTEGER | NOT NULL, DEFAULT 0 | Retry count |
| `adapter_reference` | VARCHAR(120) | NULL | External system reference |
| `error_message` | TEXT | NULL | Error details on failure |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

---

## Schema: `audit` — Audit Trail

Tables: `audit_ledger`, `pii_token_map`

### audit.audit_ledger

Hash-chained tamper-evident audit ledger.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `seq` | BIGINT | UNIQUE, Identity() | Strict chain ordering sequence |
| `session_id` | UUID | INDEX, NULL | Agent session |
| `event_type` | VARCHAR(40) | NOT NULL | Event type identifier |
| `entity_reference` | VARCHAR(120) | NULL | Referenced entity |
| `payload` | JSONB | NOT NULL | Event payload (GIN indexed) |
| `previous_hash` | CHAR(64) | NOT NULL | SHA-256 of previous entry |
| `entry_hash` | CHAR(64) | NOT NULL | SHA-256 of this entry |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### audit.pii_token_map

Token-to-PII mapping for masked data (encrypted).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `token` | VARCHAR(80) | NOT NULL, UNIQUE | Token identifier |
| `pii_type` | VARCHAR(20) | NOT NULL, CHECK IN ('msisdn','national_id','email','name','iccid') | PII type |
| `encrypted_value` | BYTEA | NOT NULL | Encrypted PII value |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## Schema: `reference` — Reference Catalogs

Tables: `business_rules`, `error_catalog`, `products`, `recharge_catalog`

### reference.business_rules

Versioned policy rule definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `rule_id` | VARCHAR(80) | NOT NULL, UNIQUE | Rule identifier |
| `domain` | VARCHAR(40) | NOT NULL | Policy domain |
| `description` | TEXT | NULL | Rule description |
| `definition_json` | JSONB | NOT NULL, DEFAULT '{}' | Rule definition (GIN indexed) |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Rule version |
| `active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Updated timestamp |

### reference.error_catalog

Canonical localized error messages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `code` | VARCHAR(80) | NOT NULL, UNIQUE | Error code |
| `domain` | VARCHAR(40) | NULL | Error domain |
| `message_fr` | TEXT | NULL | French message |
| `message_ar` | TEXT | NULL | Arabic message |
| `message_en` | TEXT | NULL | English message |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### reference.products

Plan/product catalog.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `product_code` | VARCHAR(50) | NOT NULL, UNIQUE | Product code |
| `name` | VARCHAR(120) | NOT NULL | Product name |
| `plan_type` | VARCHAR(20) | NOT NULL, CHECK IN ('PREPAID','POSTPAID') | Plan type |
| `active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

### reference.recharge_catalog

Prepaid recharge denominations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `code` | VARCHAR(50) | NOT NULL, UNIQUE | Recharge code |
| `amount` | NUMERIC(12,2) | NOT NULL | Recharge amount |
| `bonus_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Bonus amount |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Created timestamp |

---

## SQL View

### crm.v_subscription_live

Created in migration `0001`. Presents a read-through view joining subscriptions with live balances.

```sql
CREATE OR REPLACE VIEW crm.v_subscription_live AS
SELECT
    s.id AS subscription_id,
    s.customer_id,
    s.msisdn,
    s.plan_type,
    s.status,
    b.balance_type,
    b.balance_value,
    b.balance_unit,
    b.expiry_date
FROM crm.subscriptions s
LEFT JOIN ocs.balance_accounts b ON b.subscription_id = s.id
WHERE s.deleted_at IS NULL;
```

---

## GIN Indexes (Migration `0008_gin_indexes`)

JSONB columns indexed for `@>` (contains) and `?` (key exists) queries.

| Index Name | Schema | Table | Column |
|-----------|--------|-------|--------|
| `ix_policy_verdicts_inputs_gin` | policy | policy_verdicts | inputs_snapshot |
| `ix_action_ledger_parameters_gin` | execution | action_ledger | parameters |
| `ix_escalation_cases_dossier_gin` | conversation | escalation_cases | dossier |
| `ix_audit_ledger_payload_gin` | audit | audit_ledger | payload |
| `ix_business_rules_definition_gin` | reference | business_rules | definition_json |
| `ix_provisioning_requests_parameters_gin` | provisioning | provisioning_requests | parameters |

---

## Migration Chain Summary

| # | Revision | Parent | Created Tables |
|---|--------|--------|---------------|
| 1 | `0001_initial` | — | Extensions, 12 schemas, `set_updated_at()` func, `crm.customers`, `crm.subscriptions`, `billing.accounts`, `billing.invoices`, `ocs.balance_accounts`, `crm.v_subscription_live` view |
| 2 | `0002_safety_core` | `0001` | `policy.policy_verdicts`, `execution.action_ledger`, `audit.audit_ledger`, `audit.pii_token_map` |
| 3 | `0003_conversation` | `0002` | `conversation.call_sessions`, `conversation.turns`, `conversation.sentiment_samples`, `conversation.escalation_cases`, `conversation.callback_schedules` |
| 4 | `0004_domain_writes` | `0003` | `billing.payments`, `billing.payment_plans`, `ocs.recharges`, `sim.block_unblock_cases` |
| 5 | `0005_ticketing_notif` | `0004` | `ticketing.tickets`, `billing.notifications` |
| 6 | `0006_reference` | `0005` | `reference.business_rules`, `reference.error_catalog`, `reference.products`, `reference.recharge_catalog` |
| 7 | `0007_oss_provisioning` | `0006` | `oss.network_elements`, `oss.alarms`, `oss.outages`, `provisioning.provisioning_requests`, `provisioning.sim_orders`, `provisioning.plan_change_history` |
| 8 | `0008_gin_indexes` | `0007` | 6 GIN indexes (no new tables) |

---

## Quick Reference: Table Count by Schema

| Schema | Tables | Purpose |
|--------|--------|---------|
| `crm` | 4 | Customer identity, subscriptions, consent, interactions |
| `billing` | 6 | Accounts, invoices, items, payments, plans, notifications |
| `ocs` | 2 | Prepaid balances, recharges |
| `sim` | 1 | SIM block/unblock cases |
| `oss` | 3 | Network elements, alarms, outages |
| `provisioning` | 3 | Provisioning requests, SIM orders, plan changes |
| `ticketing` | 1 | GLPI ticket mirror |
| `conversation` | 5 | Call sessions, turns, sentiment, escalations, callbacks |
| `policy` | 1 | Policy verdicts |
| `execution` | 1 | Action ledger |
| `audit` | 2 | Hash-chained audit log, PII token map |
| `reference` | 4 | Business rules, error catalog, products, recharge catalog |
| **Total** | **33** | |