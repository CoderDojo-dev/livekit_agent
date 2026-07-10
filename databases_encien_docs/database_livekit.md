# Telecom AI Platform - Database Architecture & Schema Guidelines

This document outlines the rules, architecture, and structural requirements for databases within the Telecom AI Voice Agent Platform. It serves as a production-ready guideline to ensure data integrity, scalability, security, and tight integration with our Hexagonal/DDD architecture.

---

## 1. Golden Rules for Database Design in Our System

To maintain a robust, performant, and secure platform, all schemas and database implementations must adhere to the following rules:

1. **Separation of Concerns (Polyglot Persistence):** 
   - **Postgres:** Strict relational data (CRM, Billing state, Subscriptions, Action logs).
   - **Redis:** Highly volatile, ephemeral state (Session State, Caching, Context aggregation across agent handoffs).
   - **Qdrant:** High-dimensional vector embeddings for RAG/Knowledge Base.
   - **MinIO/S3:** Immutable blob storage (Audio records, call receipts, large file attachments).

2. **Security & PII Regulations:**
   - Personally Identifiable Information (PII) such as National ID/CIN, MSISDN (phone numbers), and emails must be treated carefully. Implement data masking at the service level before logging.
   - Database user roles must follow the principle of least privilege. Microservices must only have access to their specific domain tables.

3. **Immutability & Auditing:**
   - Operational logs, LLM decisions, and executed actions (via Execution Service) MUST NOT be mutated or hard-deleted. Use append-only tables or soft deletes (`deleted_at` timestamp).
   - Every major CRM change requires strong auditing (who, what, when).

4. **Foreign Keys & Consistency:**
   - Use strict foreign keys in Postgres to maintain referential integrity.
   - Always use UUIDs (`uuid_generate_v4()`) for primary keys instead of auto-incrementing integers to ensure security and prevent enumeration attacks.

5. **Timestamping & Timezones:**
   - Standardize all schema timestamps on `TIMESTAMP WITH TIME ZONE` (UTC). 
   - Every relational table must include `created_at` and `updated_at` fields.

---

## 2. Relational Schema Structure (PostgreSQL)

Below is the production-ready schema design for the core organizational and operational tables. 

### A. Customer Domain (`context-service` / CRM)
Manage user identities, telecom profiles, and KYC data.

```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    national_id VARCHAR(50) UNIQUE NOT NULL, -- CIN/Passport
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    contact_number VARCHAR(20),
    preferred_language VARCHAR(10) DEFAULT 'fr', -- fr, en, ar
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    msisdn VARCHAR(20) UNIQUE NOT NULL, -- The connected phone number
    plan_type VARCHAR(50) NOT NULL, -- e.g., 'POSTPAID', 'PREPAID'
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, BLOCKED
    roaming_enabled BOOLEAN DEFAULT FALSE,
    data_balance_mb INTEGER DEFAULT 0,
    voice_balance_min INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### B. Session & Escalation Domain (`agent-worker`)
Track live intelligence, agent routing, and sentiment frustration limits (Phase 8).

```sql
CREATE TABLE call_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    msisdn VARCHAR(20) NOT NULL, -- Caller ID
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    final_disposition VARCHAR(50), -- e.g., 'RESOLVED', 'ESCALATED', 'DROPPED'
    max_frustration_score DECIMAL(5, 2) DEFAULT 0.0, -- Max sentiment score logged
    audio_record_url TEXT, -- MinIO path
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE callback_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES call_sessions(id),
    msisdn VARCHAR(20) NOT NULL,
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, COMPLETED, CANCELLED
    priority_level INT DEFAULT 1, -- Determined by sentiment/frustration
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### C. Decision & Execution Domain (`decision-service`)
Persist determinist actions that require tracking for billing/troubleshooting.

```sql
CREATE TABLE action_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES call_sessions(id),
    agent_type VARCHAR(50) NOT NULL, -- e.g., 'BillingAgent', 'ManagerAgent'
    action_type VARCHAR(100) NOT NULL, -- e.g., 'SIM_UNLOCK', 'ROAMING_ACTIVATION', 'TRANSFER_SIP'
    parameters JSONB NOT NULL, -- The arguments generated by LLM
    policy_approved BOOLEAN NOT NULL, -- Passed deterministic ruleset?
    execution_status VARCHAR(50), -- SUCCESS, FAILED, PENDING
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 3. Ephemeral Architecture (Redis & Memcached)

**Use Case:** Real-time state aggregation to bridge millisecond delays in Voice-to-Voice LLM interactions.

*   **`session:{session_id}:state`** (Hash)
    - Replaces native Python lists/dictionaries for multi-agent capability.
    - Stores `consecutive_negative_turns`, `clarification_loops`, and current assigned Agent (Triage, Technical).
    - **Rule:** Absolute TTL must be set to `2 hours` post-call to free memory limits securely.
    
*   **`context:{msisdn}:live`** (JSON/Hash)
    - Highly fetched network data (current megabytes remaining, network tower status).
    - **Rule:** Fetched via Context Service into Redis for the duration of the call, then evicted.
    
---

## 4. Vectorized RAG Structure (Qdrant)

**Use Case:** The `services/knowledge-service` corpus retrieval. 

*   **Collection:** `telecom_technical_guidelines`
*   **Vector Rules:**
    - Models should strictly utilize chunk sizes (e.g., 512-1024 tokens) optimized for retrieval precision.
    - **Payload Filters:** Every vector must include the following metadata payloads:
        - `document_type`: (e.g., 'ROAMING_POLICY', 'HARDWARE_RESET')
        - `applicable_plans`: List of plans (e.g., ['PREPAID', 'POSTPAID'])
        - `language`: (fr, en, ar) to match the customer’s `preferred_language`.

---

## 5. Next Implementation Steps (CRM/Mock Switchover)

As specified in Phase 7.5 & 9 Roadmaps:
1. Implement SQLAlchemy ORM models matching the Postgres schemas.
2. Replace local volatile lists (e.g., `mock_directory.py`) in `context-service` with active DB Engine session dependencies.
3. Migrate the ephemeral session logic (`session_state.py`) entirely using `redis-py`.
4. Enact automated database migration handling framework (e.g., Alembic for Python) to version-control all upcoming CRM changes.
