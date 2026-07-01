# Backend Engineer — Implementation Tasks: Missing, Empty & Stub Components

> **Date:** 2026-06-30  
> **Purpose:** Every component that needs to be built, fixed, or wired to make the system production-complete.  
> **Scope:** No test work — only production code, schemas, adapters, infrastructure, and security.

---

## How to Use This Document

Each section lists a concrete gap with:
- **Location** — exact file path(s) in the codebase
- **What exists now** — current state of the code
- **What must be built** — the implementation required
- **Effect on the system** — why this matters
- **Priority** — 🔴 Critical / 🟠 High / 🟡 Medium / ⚪ Enhancement

---

## TABLE OF CONTENTS

1. [Empty Schemas (OSS & Provisioning)](#1-empty-schemas-oss--provisioning)
2. [Empty MCP Server (Messaging Gateway)](#2-empty-mcp-server-messaging-gateway)
3. [Stub Adapter Package (Integration-Adapters)](#3-stub-adapter-package-integration-adapters)
4. [Real GLPI REST Client (Ticketing)](#4-real-glpi-rest-client-ticketing)
5. [Real SMS/WhatsApp/Email Channels (Notification)](#5-real-smswhatsappemail-channels-notification)
6. [Real Qdrant Vector Search (Knowledge Service)](#6-real-qdrant-vector-search-knowledge-service)
7. [Real Redis Caching Layer](#7-real-redis-caching-layer)
8. [Real MinIO Audio Recording Storage](#8-real-minio-audio-recording-storage)
9. [AccountServicesAgent Stub](#9-accountservicesagent-stub)
10. [Execution-Service Mock Dispatch](#10-execution-service-mock-dispatch)
11. [Notification-Client Stub](#11-notification-client-stub)
12. [Dead Code: mock_directory.py & aggregator.py](#12-dead-code-mock_directorypy--aggregatorpy)
13. [Connection Pool Configuration Missing](#13-connection-pool-configuration-missing)
14. [Missing GIN Indexes on JSONB Columns](#14-missing-gin-indexes-on-jsonb-columns)
15. [CORS Wide Open in Token-Service](#15-cors-wide-open-in-token-service)
16. [Default Credentials in .env.example & Compose](#16-default-credentials-in-envexample--compose)
17. [No Service-to-Service Authentication](#17-no-service-to-service-authentication)
18. [No API Gateway](#18-no-api-gateway)
19. [Missing CI/CD Pipeline](#19-missing-cicd-pipeline)
20. [Missing Kubernetes Helm Charts](#20-missing-kubernetes-helm-charts)
21. [Missing Docker Healthchecks](#21-missing-docker-healthchecks)
22. [Missing DB Backup & Restore Scripts](#22-missing-db-backup--restore-scripts)
23. [Missing Secrets Management](#23-missing-secrets-management)
24. [Build Artifacts Committed to Repo](#24-build-artifacts-committed-to-repo)
25. [No mypy Type Checking Configuration](#25-no-mypy-type-checking-configuration)
26. [No Ruff Linting Configuration in pyproject.toml](#26-no-ruff-linting-configuration-in-pyprojecttoml)
27. [AccountServicesAgent Imports Wrong Base Class](#27-accountservicesagent-imports-wrong-base-class)
28. [Typo in Patches Directory Name](#28-typo-in-patches-directory-name)
29. [Missing Database Migration Tests Automation](#29-missing-database-migration-tests-automation)
30. [Missing Production Dockerfiles for Services](#30-missing-production-dockerfiles-for-services)
31. [Dead Test in Resilience Suite](#31-dead-test-in-resilience-suite)

---

## 1. Empty Schemas (OSS & Provisioning)

### Location
```
packages/persistence/src/persistence/models/
  (no oss.py, no provisioning.py files exist)
  
alembic/versions/0001_initial_crm_billing_ocs.py
  Line ~20: "oss", "provisioning" listed in SCHEMAS but no tables
```

### What exists now
Both `oss` and `provisioning` schemas are created empty in migration 0001. They exist as 
PostgreSQL namespaces with zero tables. No model files exist for them.

### What must be built

**File to create:** `packages/persistence/src/persistence/models/oss.py`
```python
"""OSS schema — network equipment inventory, alarms, outages."""
from persistence.base import Base, UUIDPrimaryKey, Timestamps

class NetworkElement(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "network_elements"
    __table_args__ = ({"schema": "oss"},)
    # Fields: element_type, vendor, model, status, location, ip_address, ...
    ...

class Alarm(UUIDPrimaryKey, Base):
    __tablename__ = "alarms"
    __table_args__ = ({"schema": "oss"},)
    # Fields: network_element_id, severity, alarm_type, description, acknowledged_at, ...
    ...

class Outage(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "outages"
    __table_args__ = ({"schema": "oss"},)
    # Fields: area, start_time, end_time, affected_services, resolved, ...
    ...
```

**File to create:** `packages/persistence/src/persistence/models/provisioning.py`
```python
"""Provisioning schema — service activation, plan changes, SIM orders."""
from persistence.base import Base, UUIDPrimaryKey, Timestamps

class ProvisioningRequest(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "provisioning_requests"
    __table_args__ = ({"schema": "provisioning"},)
    # Fields: subscription_id, action_type, status, requested_at, completed_at, ...
    ...

class SimOrder(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "sim_orders"
    __table_args__ = ({"schema": "provisioning"},)
    # Fields: customer_id, sim_type, iccid, status, tracking_code, ...
    ...

class PlanChangeHistory(UUIDPrimaryKey, Base):
    __tablename__ = "plan_change_history"
    __table_args__ = ({"schema": "provisioning"},)
    # Fields: subscription_id, from_plan, to_plan, changed_by, effective_date, ...
    ...
```

**Register the models** in `packages/persistence/src/persistence/models/__init__.py`:
```python
from persistence.models import oss, provisioning  # add these two
```

**Create migration** `alembic/versions/0007_oss_provisioning.py`:
```python
"""oss + provisioning tables."""
revision = "0007_oss_provisioning"
down_revision = "0006_reference"
```

### Effect on the system
- Without these schemas, the system cannot track network outages, alarms, SIM inventory, or 
  plan change history
- The action type `CHANGE_PLAN` maps to `provisioning` domain but no table exists to record it
- OSS data is required for the `NmsAdapter` port to function — currently raises `NotImplementedError`

### Priority: 🟠 High

---

## 2. Empty MCP Server (Messaging Gateway)

### Location
```
mcp-servers/messaging-gateway/
  (only top-level directory exists — no src/, no pyproject.toml, no files)
```

### What exists now
A named directory with zero files. The `PHASE-7-README` flagged this as a placeholder.

### What must be built

**Create:** `mcp-servers/messaging-gateway/pyproject.toml`
```toml
[project]
name = "messaging-gateway"
version = "0.1.0"
description = "MCP server for outbound SMS/WhatsApp/Email via the notification-service."
dependencies = ["mcp>=1.0.0", "httpx"]
```

**Create:** `mcp-servers/messaging-gateway/src/messaging_gateway/server.py`
```python
"""Messaging gateway MCP — exposes send_sms, send_whatsapp, send_email tools.
Proxies to the notification-service (:8106) for actual dispatch."""
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("messaging-gateway", host="0.0.0.0", port=8301)
# Tool: send_sms(to, body) → POST /notify to notification-service
# Tool: send_whatsapp(to, body) → POST /notify to notification-service
# Tool: send_email(to, subject, body) → POST /notify to notification-service
```

**Register** in `apps/agent-worker/src/config/settings.py` — add `MESSAGING_MCP_URL`.

**Wire** in the agent-worker: create `mcp_clients/messaging_toolset.py` and add it to 
appropriate agent personas.

### Effect on the system
- No programmatic outbound messaging tool exists for the LLM agents
- The notification-service has SMS/Email **sending** capability, but no **tool** to invoke it 
  from the voice agent
- Agents cannot send written confirmations directly (they must rely on the ticketing MCP)

### Priority: 🟠 High

---

## 3. Stub Adapter Package (Integration-Adapters)

### Location
```
packages/integration-adapters/src/integration_adapters/
├── __init__.py          # 5 lines — docstring only
├── billing_adapter.py   # 23 lines — raises NotImplementedError
├── crm_adapter.py       # 18 lines — raises NotImplementedError
├── glpi_adapter.py      # 18 lines — raises NotImplementedError
├── nms_adapter.py       # 16 lines — raises NotImplementedError
├── ocs_adapter.py       # 23 lines — raises NotImplementedError
└── payment_adapter.py   # 15 lines — raises NotImplementedError
```

Total: **78 lines, 6 classes, 12 methods — ALL raise NotImplementedError**

### What exists now
Every adapter class has a constructor that accepts `base_url` and methods that raise 
`NotImplementedError("wired in Phase X")`. Phases 4–9 have shipped but these were never 
filled in. The `domain-core` ports they implement are fully defined.

### What must be built

Each adapter must be implemented as a real HTTP client to the corresponding external system. 
The pattern is consistent:

**BillingAdapter** (`billing_adapter.py`):
- `get_open_invoices(customer_id)` → `GET {base_url}/invoices?customer_id={id}&status=open`
- `charge(customer_id, amount, key)` → `POST {base_url}/charges` with idempotency key
- `grant_deferral(customer_id, days, key)` → `POST {base_url}/deferrals`

**OcsAdapter** (`ocs_adapter.py`):
- `get_balance(customer_id)` → query the OCS balance API
- `top_up(customer_id, amount, key)` → submit a recharge to the OCS
- `apply_data_addon(customer_id, addon_id, key)` → activate a data package

**GlpiAdapter** (`glpi_adapter.py`):
- `create_ticket(subject, body, priority)` → `POST /apirest.php/Ticket` (GLPI REST API)
- `get_ticket_status(ticket_id)` → `GET /apirest.php/Ticket/{id}`

**CrmAdapter** (`crm_adapter.py`):
- `get_client_by_msisdn(msisdn)` → queries the CRM API
- `get_client_by_id(customer_id)` → queries the CRM API

**PaymentAdapter** (`payment_adapter.py`):
- `pay(token, amount, key)` → charges a payment gateway (Stripe, Tunisie Payment, etc.)

**NmsAdapter** (`nms_adapter.py`):
- `get_network_status(area)` → queries the network monitoring system

All should use `httpx.AsyncClient` with configurable timeouts and retry logic.

**Important:** Add a configuration switch `CONNECTOR_MODE` (env var) that selects between 
`mock` and `live` mode for each adapter. The `mock` mode preserves existing behaviour (mostly 
the execution-service `dispatch()` function). `live` mode calls the real HTTP endpoints.

### Effect on the system
- **Every sensitive action** (payment, SIM unblock, recharge, plan change, ticket creation) 
  currently generates fake references like `PAY-ABC123DEF` — no real side effects occur
- The system can demo but cannot transact
- This is the single highest-impact implementation task

### Priority: 🔴 Critical

---

## 4. Real GLPI REST Client (Ticketing)

### Location
```
mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/glpi_client.py
  Lines 21–47 — MockGlpiClient with in-memory dict store
```

### What exists now
`MockGlpiClient` stores tickets in a Python dictionary. On restart, all tickets are lost. 
The 4 tools (`create_ticket`, `get_ticket_status`, `resolve_ticket`, `lookup_tickets`) 
operate entirely in memory.

### What must be built

**Rewrite** `glpi_client.py` to implement a real GLPI REST API client:

```python
class GlpiClient:
    """Real GLPI REST API client using session token authentication."""
    
    def __init__(self, base_url: str, app_token: str, user_token: str):
        self._base_url = base_url
        self._session_token = None
        # POST /apirest.php/initSession to get session token
    
    def _init_session(self):
        """POST /apirest.php/initSession with App-Token + Authorization."""
    
    def create(self, customer_id, subject, description) -> Ticket:
        """POST /apirest/Ticket with input data."""
    
    def get(self, ticket_id) -> Ticket | None:
        """GET /apirest/Ticket/{id}."""
    
    def resolve(self, ticket_id, resolution) -> Ticket | None:
        """PUT /apirest/Ticket/{id} with solution."""
    
    def list_for(self, customer_id) -> list[Ticket]:
        """GET /apirest/Ticket?criteria[0][field]=..."""
```

**Add environment variables** to the ticketing-glpi server:
- `GLPI_BASE_URL` — the GLPI instance URL
- `GLPI_APP_TOKEN` — GLPI application API token
- `GLPI_USER_TOKEN` — GLPI user API token

**Add a configuration switch** `CONNECTOR_MODE=mock|live` to toggle between MockGlpiClient 
and the real GlpiClient.

### Effect on the system
- Tickets created by the AI agent are **lost on restart** — no persistence
- Cannot integrate with a real IT helpdesk
- The GLPI ticketing system is a core requirement (§5.9 of the spec)

### Priority: 🔴 Critical

---

## 5. Real SMS/WhatsApp/Email Channels (Notification)

### Location
```
services/notification-service/src/notification_service/channels.py
  Lines 32–41 — MockSmsChannel, MockWhatsAppChannel, MockEmailChannel
  All three inherit _MockChannel which logs the message to console
```

### What exists now
Three mock channels: they log the message body via `logger.info()` and return a fake reference 
like `SMS-ABC123DEF`. No real message is sent.

### What must be built

**Replace** the mock channels with real provider integrations. Keep the existing mock classes 
for dev mode behind a `CONNECTOR_MODE=live` switch.

**SMS channel** — use Twilio or Infobip:
```python
class TwilioSmsChannel:
    name = "sms"
    async def send(self, to: str, body: str) -> str:
        # from twilio.rest import Client
        # message = self._client.messages.create(to=to, from_=self._from, body=body)
        # return message.sid
```

**WhatsApp channel** — use Twilio WhatsApp or WhatsApp Business API:
```python
class TwilioWhatsAppChannel:
    name = "whatsapp" 
    async def send(self, to: str, body: str) -> str:
        # to = f"whatsapp:{to}"
        # message = self._client.messages.create(to=to, from_=self._from, body=body)
        # return message.sid
```

**Email channel** — use SendGrid, SMTP, or SES:
```python
class SendGridEmailChannel:
    name = "email"
    async def send(self, to: str, body: str) -> str:
        # from sendgrid import SendGridAPIClient
        # response = self._client.send(message)
        # return str(response.status_code)
```

**Add environment variables:**
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM`
- `SENDGRID_API_KEY`, `EMAIL_FROM`
- Or equivalent for the chosen provider

**Update `channels.py`** to select mock vs live based on `CONNECTOR_MODE`.

### Effect on the system
- Customers never receive SMS confirmations for tickets, payments, or callbacks
- The notification-service exists but produces zero real notifications
- Written confirmation is a core requirement (§4.10)

### Priority: 🔴 Critical

---

## 6. Real Qdrant Vector Search (Knowledge Service)

### Location
```
services/knowledge-service/src/knowledge_service/retriever.py
  Lines 30–49 — LexicalRetriever (keyword overlap scoring, no embeddings)
services/knowledge-service/src/knowledge_service/corpus.py
  Lines 22–75 — in-memory CORPUS tuple of 5 hardcoded documents

env vars reference: QDRANT_URL (in .env.example) but no code uses it
```

### What exists now
The `LexicalRetriever` does simple token overlap scoring against 5 hardcoded documents. 
No vector embeddings, no Qdrant collection, no chunking pipeline. The Qdrant container 
runs but nothing writes to or reads from it. The in-memory corpus is lost on restart.

### What must be built

**1. Create an embedding pipeline** that chunks the corpus, generates embeddings (using 
OpenAI's `text-embedding-3-small` or a local model via `sentence-transformers`), and 
upserts them into Qdrant:
```python
# services/knowledge-service/src/knowledge_service/indexer.py
class QdrantIndexer:
    def __init__(self, qdrant_url: str, collection_name: str = "telecom_knowledge"):
        self._client = QdrantClient(qdrant_url)
    
    async def ensure_collection(self):
        # Create collection with 1536-dim vectors (OpenAI) or 384-dim (sentence-transformers)
    
    async def index_documents(self, documents: list[Document]):
        # Chunk + embed + upsert to Qdrant
    
    async def search(self, query: str, top_k: int = 4) -> list[Passage]:
        # Embed query → search Qdrant → return scored passages
```

**2. Create a `QdrantRetriever`** implementing the same interface as `LexicalRetriever`:
```python
class QdrantRetriever:
    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        """Embed query, search Qdrant, return scored passages."""
```

**3. Add a configuration switch** in the knowledge-service to select between 
`LexicalRetriever` (dev) and `QdrantRetriever` (production).

**4. Load the corpus** from a file or the reference schema instead of hardcoded tuples.

### Effect on the system
- Knowledge retrieval is limited to 5 hardcoded FAQ entries with keyword-only search
- No semantic understanding — "how do I pay my bill" and "invoice payment procedure" don't 
  match despite being the same question
- The entire Qdrant infrastructure (container port 6333) is wasted

### Priority: 🟠 High

---

## 7. Real Redis Caching Layer

### Location
```
.env.example — references REDIS_URL=redis://localhost:6379/0
infra/docker-compose/docker-compose.yml — redis container runs on port 6379
apps/agent-worker/src/config/settings.py — no Redis config
services/context-service/src/context_service/repositories.py — no Redis
```

### What exists now
Redis server runs as a Docker container but **zero code reads or writes to it**. Every 
service loads all data fresh on every request. The Customer-360 snapshot is fetched from 
Postgres on every call. Session state is in-memory only (lost if the worker restarts).

### What must be built

**1. Create a Redis cache utility** in a shared package:
```
packages/cache/
├── src/cache/
│   ├── __init__.py
│   ├── redis_client.py     # Redis connection pool + helper functions
│   └── ttl.py              # TTL constants per data type
```

**2. Cache the Customer-360 snapshot** in the context-service:
```python
# In context-service CrmRepository.build_customer360():
#   cached = await redis.get(f"customer360:{msisdn}")
#   if cached: return Customer360(**json.loads(cached))
#   ... build from DB ...
#   await redis.setex(f"customer360:{msisdn}", 300, snapshot.json())  # 5 min TTL
```

**3. Cache session state** in the agent-worker:
```python
# Instead of dict in memory:
#   await redis.hset(f"session:{session_id}:state", mapping={...})
# Survives worker restarts, enables horizontal scaling
```

**4. Cache idempotency keys** for fast duplicate detection before the DB write.

**5. Add TTL constants** — Customer-360: 5 min, session state: 2 hours (post-call eviction), 
idempotency keys: 24 hours.

### Effect on the system
- Every call is slower than necessary (full DB query every time)
- Worker restart loses all in-progress session state
- Horizontal scaling is impossible (in-memory state is per-process)
- The Redis container runs idle consuming resources

### Priority: 🟠 High

---

## 8. Real MinIO Audio Recording Storage

### Location
```
.env.example — references MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
infra/docker-compose/docker-compose.yml — minio container runs on ports 9000/9001
apps/agent-worker/src/conversation/writer.py — audio_record_url is set to None in finish_session
apps/agent-worker/src/server.py — no MinIO upload on call end
```

### What exists now
MinIO server runs as a Docker container but **no code writes audio recordings to it**. 
The `CallSession.audio_record_url` field is always `null`. No bucket is created. No 
presigned URL is generated. The worker does not capture or upload audio tracks.

### What must be built

**1. Create a MinIO client** in the agent-worker:
```python
# apps/agent-worker/src/storage/audio_recorder.py
from minio import Minio

class AudioRecorder:
    def __init__(self, endpoint, access_key, secret_key, bucket="call-recordings"):
        self._client = Minio(endpoint, access_key, secret_key, secure=False)
    
    async def ensure_bucket(self):
        # Create bucket if not exists
    
    async def upload_recording(self, session_id: str, audio_data: bytes) -> str:
        # Upload to MinIO, return the object URL
    
    async def get_download_url(self, object_name: str, expires=timedelta(hours=1)):
        # Generate presigned GET URL
```

**2. Wire in `server.py`** — on call end (in `_finish_conversation`):
- Export the LiveKit room's recorded audio (via Egress API or local capture)
- Upload to MinIO
- Set `audio_record_url` on the `CallSession` row

**3. Add cleanup** to the retention job — clear MinIO objects when purging.

### Effect on the system
- Call recordings are defined in the schema but never stored
- Compliance requirement (§8.1) for recording consent is meaningless without actual 
  recording storage
- Supervisor dashboard cannot play back calls

### Priority: 🟠 High

---

## 9. AccountServicesAgent Stub

### Location
```
apps/agent-worker/src/agents/account_services_agent.py
  Line 16 — class AccountServicesAgent(Agent):  ← inherits Agent, not BaseTelecomAgent
  Line 18 — super().__init__(instructions="You handle plans, recharges and roaming.")
  No tools, no on_enter, no business logic
```

### What exists now
A one-liner class with an instruction string and zero tools. It inherits `Agent` directly 
(bypassing `BaseTelecomAgent`'s sentiment/de-escalation hooks). It cannot actually handle 
plans, recharges, or roaming.

### What must be built

**Rewrite** `account_services_agent.py`:
```python
from agents.base_agent import BaseTelecomAgent
from tools.routing_tools import route_to_billing  # etc.

class AccountServicesAgent(BaseTelecomAgent):
    """Handles account management: plan consultation/change, recharge, roaming toggle."""
    
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle account services: plan consultation, plan changes, prepaid "
                "recharges, and roaming activation/deactivation. For plan details call "
                "get_plan_details. To change a plan use change_plan. For a recharge use "
                "top_up. For roaming use toggle_roaming. For general FAQ questions call "
                "knowledge_search. Keep replies short."
            ),
            chat_ctx=chat_ctx,
            tools=[...],  # add tools for plan, recharge, roaming
        )
    
    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with account management."
        )
```

**Create the required tools:**
```
apps/agent-worker/src/tools/
├── account_tools.py  # get_plan_details, change_plan, toggle_roaming
```

### Effect on the system
- The 5th persona (account services) is unusable — if the Triage agent routes a caller 
  here, the agent has no tools to do anything
- Plan changes, recharges, and roaming toggles are promised in the routing but cannot 
  be fulfilled

### Priority: 🟠 High

---

## 10. Execution-Service Mock Dispatch

### Location
```
services/execution-service/src/execution_service/executor.py
  Lines 22–25 — dispatch() generates fake reference codes
```

### What exists now
```python
def dispatch(action_type: str, payload: dict) -> str:
    prefix = _REFERENCE_PREFIX.get(action_type, "ACT")
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"
```

This generates `PAY-ABC123DEF` without contacting any real system. The `projections.py` 
file writes domain tables (payments, recharges, SIM cases) but the actual business effect 
is mock.

### What must be built

Replace `dispatch()` with real adapter calls:

```python
_ADAPTERS = {
    "billing": BillingAdapter(settings.billing_url),
    "ocs": OcsAdapter(settings.ocs_url),
    "sim": SimAdapter(settings.nms_url),
    "provisioning": ProvisioningAdapter(settings.provisioning_url),
}

async def dispatch(action_type: str, payload: dict, customer_id=None) -> str:
    domain = target_domain(action_type)
    adapter = _ADAPTERS.get(domain)
    if adapter is None:
        raise ValueError(f"no adapter for domain {domain}")
    # Call the real adapter method
    return await adapter.execute(action_type, payload)
```

### Effect on the system
- Every "executed" action returns a fake reference — nothing actually happens
- Payment deferrals, SIM unblocks, recharges, plan changes exist in the ledger but not 
  in real systems
- Without this, the entire sensitive-action pipeline is a simulation

### Priority: 🔴 Critical

---

## 11. Notification-Client Stub

### Location
```
packages/notification-client/src/notification_client/client.py
  Lines 11–15 — entire implementation:
  
class ChannelStrategyNotifier(NotificationPort):
    async def send(self, channel, to, template, data):
        logger.info("notify channel=%s to=%s template=%s", channel, to, template)
```

### What exists now
A class that logs the notification intent and does nothing else. Total: 15 lines, 1 method, 
pure logging.

### What must be built

**Implement** a real HTTP client that calls the notification-service:

```python
class ChannelStrategyNotifier(NotificationPort):
    def __init__(self, base_url: str = "http://localhost:8106"):
        self._base_url = base_url
    
    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base_url}/notify",
                json={
                    "channel": channel,
                    "to": to,
                    "template": template,
                    "params": data,
                },
                timeout=5.0
            )
```

### Effect on the system
- No worker-originated notifications are sent
- The callback confirmation SMS promised by Phase 8 never fires
- The notification pipeline has a broken link

### Priority: 🟠 High

---

## 12. Dead Code: mock_directory.py & aggregator.py

### Location
```
services/context-service/src/context_service/
├── aggregator.py       # 50 lines — imports and uses mock_directory
├── mock_directory.py   # 99 lines — in-memory customer data
└── repositories.py     # 130 lines — CrmRepository (the real Postgres-backed class)
```

### What exists now
The `main.py` FastAPI endpoints use `CrmRepository` from `repositories.py` — the real 
Postgres-backed class. But `aggregator.py` (which uses `mock_directory`) also exists in 
the tree and is imported by the test suite (`test_aggregator.py`). The tests verify the 
mock version, not the real Postgres version.

`mock_directory.py` is **dead code for production** — it is not called by any FastAPI 
endpoint. It only exists for the offline tests.

### What must be done

1. **Delete** `services/context-service/src/context_service/mock_directory.py`
2. **Rewrite** `services/context-service/src/context_service/aggregator.py` to use 
   `CrmRepository` instead of `mock_directory` (or simply delete and let tests use 
   the repository directly)
3. **Rewrite** `test_aggregator.py` to test `CrmRepository` against Postgres, or 
   keep an in-memory version if needed for offline testing

### Effect on the system
- Dead code creates confusion about which data path is active
- Tests verify the mock layer, not the production layer — false confidence
- Maintenance burden: two parallel implementations must be kept in sync

### Priority: 🟡 Medium

---

## 13. Connection Pool Configuration Missing

### Location
```
packages/persistence/src/persistence/engine.py
  Line 26: _engine = create_engine(url, pool_pre_ping=True, future=True)
  No pool_size, no max_overflow, no pool_timeout
```

### What exists now
`create_engine()` is called with only `pool_pre_ping=True`. The default pool size is 5 
and `max_overflow` is 10, but these are SQLAlchemy defaults, not explicit config. Under 
load, connections can spike without bound.

### What must be done

Add environment-driven pool configuration:
```python
def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "postgresql+psycopg://telecom:telecom@localhost:5432/telecom")
        _engine = create_engine(
            url,
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.getenv("DB_POOL_TIMEOUT", "30.0")),
            pool_pre_ping=True,
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
            future=True,
        )
    return _engine
```

### Effect on the system
- Under concurrent call load, the connection pool may exhaust server connections
- No `pool_recycle` means stale connections accumulate
- Hard to tune for production without env-driven configuration

### Priority: 🟡 Medium

---

## 14. Missing GIN Indexes on JSONB Columns

### Location
```
packages/persistence/src/persistence/models/
├── audit.py — audit_ledger.payload is JSONB, no GIN index
├── conversation.py — escalation_cases.dossier is JSONB, no GIN index
├── execution.py — action_ledger.parameters is JSONB, no GIN index
```

### What exists now
Several tables have JSONB columns for flexible payloads, but none have GIN indexes. 
Without GIN indexes, `@>` and `?` JSON queries will be sequential scans.

### What must be done

Add GIN indexes in a new migration `0008_gin_indexes.py`:
```python
def upgrade():
    op.create_index("ix_audit_ledger_payload_gin", "audit_ledger", ["payload"], 
                    postgresql_using="gin", schema="audit")
    op.create_index("ix_escalation_cases_dossier_gin", "escalation_cases", ["dossier"], 
                    postgresql_using="gin", schema="conversation")
    op.create_index("ix_action_ledger_parameters_gin", "action_ledger", ["parameters"], 
                    postgresql_using="gin", schema="execution")
    op.create_index("ix_policy_verdicts_inputs_gin", "policy_verdicts", ["inputs_snapshot"], 
                    postgresql_using="gin", schema="policy")
```

### Effect on the system
- Queries filtering on JSONB content degrade to sequential scans at modest table sizes
- Supervisor dashboard queries for escalation dossiers will be slow

### Priority: 🟡 Medium

---

## 15. CORS Wide Open in Token-Service

### Location
```
apps/token-service/src/token_service/main.py
  Lines 24–29:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev only
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### What exists now
`allow_origins=["*"]` allows any website to call the token-service. Comment says "dev only" 
but no mechanism restricts it in staging/production.

### What must be done

Replace the wildcard with an environment-driven allow-list:
```python
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
```

In production, set `CORS_ORIGINS=https://widget.telecom.tn,https://dashboard.telecom.tn`.

### Effect on the system
- Any external website can mint tokens and connect to the LiveKit server
- Token theft allows unauthorized calls that consume AI API credits

### Priority: 🔴 Critical

---

## 16. Default Credentials in .env.example & Compose

### Location
```
.env.example:
  LIVEKIT_API_KEY=devkey
  LIVEKIT_API_SECRET=devsecret_change_me

infra/docker-compose/docker-compose.yml:
  LIVEKIT_KEYS: "devkey: devsecret_change_me"
  
  postgres:
    POSTGRES_USER: telecom
    POSTGRES_PASSWORD: telecom
  
  minio:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
```

### What exists now
Default credentials are hardcoded in the compose file and .env.example. The Postgres 
password is `telecom`, MinIO is `minioadmin`, LiveKit is `devsecret_change_me`. If 
deployed as-is, the system is trivially compromisable.

### What must be done

1. **Remove passwords from docker-compose.yml** — reference env vars instead:
```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

2. **Generate strong defaults** in a setup script

3. **Add a `make secure-deploy`** target that generates random passwords

4. **Document** required env vars for production deployment

### Effect on the system
- Anyone who can reach the Docker network can access the database, MinIO, and LiveKit
- Data breach risk

### Priority: 🔴 Critical

---

## 17. No Service-to-Service Authentication

### Location
```
All service clients in apps/agent-worker/src/clients/:
├── context_client.py     # httpx to :8101 — no auth header
├── decision_client.py    # httpx to :8103 — no auth header
├── execution_client.py   # httpx to :8105 — no auth header
├── policy_client.py      # httpx to :8104 — no auth header
├── notification_client.py # httpx to :8106 — no auth header
└── routing_client.py     # httpx (future) — no auth header

All FastAPI service main.py files — no middleware checks
```

### What exists now
Every inter-service HTTP call is unauthenticated. Any process that can reach the internal 
network can call any service endpoint. There is no token validation, no API key, no mTLS.

### What must be built

**1. Add an internal API key** to every service, read from env:
```python
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
```

**2. Add dependency** to every service route:
```python
from fastapi import Header, HTTPException

async def verify_internal_key(x_api_key: str = Header(...)):
    if x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
```

**3. Add the key to every client**:
```python
self._client = httpx.AsyncClient(
    base_url=base_url,
    headers={"X-API-Key": settings.internal_api_key},
    timeout=timeout,
)
```

### Effect on the system
- Any compromised container can read all customer data via the internal APIs
- No audit trail of which service called which endpoint
- Regulatory compliance risk (PCI-DSS, GDPR)

### Priority: 🔴 Critical

---

## 18. No API Gateway

### Location
```
infra/ — no API gateway config (no nginx, no Kong, no Traefik, no Envoy)
apps/ — each service is independently exposed
```

### What exists now
All services expose their ports directly (`:8101` through `:8107`, `:8201`, `:8202`). 
There is no unified entry point, no rate limiting, no TLS termination, no request 
validation at the edge.

### What must be built

Add an API gateway to `infra/docker-compose/docker-compose.yml`:

```yaml
gateway:
  image: nginx:alpine  # or traefik, kong, envoy
  ports:
    - "443:443"   # external
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
  depends_on:
    - business-api
    - token-service
    - context-service
```

The gateway should:
- Route `/api/v1/*` → business-api (`:8108`)
- Route `/token` → token-service (`:8107`)
- Route `/context/*` → context-service (`:8101`)
- Terminate TLS
- Apply rate limiting
- Validate required headers (X-API-Key)

### Effect on the system
- Every service must be individually secured and exposed
- No rate limiting means a single abusive caller can overload the system
- No centralized TLS termination
- Hard to implement authentication/authorization consistently

### Priority: 🟠 High

---

## 19. Missing CI/CD Pipeline

### Location
```
infra/ci-cd/README.md — one line describing what a pipeline should look like
No .github/workflows/, no Jenkinsfile, no GitLab CI, no Makefile targets for CI
```

### What exists now
A single-line README: "Pipeline per module: build → unit → contract → image+scan → deploy".

### What must be built

Create `.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: telecom
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e packages/persistence
      - run: (cd packages/persistence && alembic upgrade head)
      - run: pip install -e packages/audit-trail
      - run: ... (install all packages)
      - run: python -m pytest ... (run all tests)
      - run: ./tests/load/loadtest.py --url ... (load gate)
```

### Effect on the system
- No automated quality gate — broken code can be merged
- No container image build — deployment is manual copy
- No automated deploy — staging and production drift apart

### Priority: 🟠 High

---

## 20. Missing Kubernetes Helm Charts

### Location
```
infra/helm/ — contains only README.md with: "Populated in Phase 12 (staging/prod)."
```

### What exists now
Phase 12 shipped but the helm charts are still a placeholder README. No actual chart 
directory exists for any service.

### What must be built

Create charts:
```
infra/helm/
├── agent-worker/     # Chart for the LiveKit agent worker
├── business-api/     # Chart for the business-api FastAPI service
├── context-service/  # Chart for context-service
├── decision-service/ # Chart for decision-service
├── execution-service/# Chart for execution-service
├── policy-service/   # Chart for policy-service
├── notification-service/ # Chart for notification-service
├── knowledge-service/# Chart for knowledge-service
├── token-service/    # Chart for token-service
├── ticketing-glpi/   # Chart for MCP server
├── ai-knowledge-rag/ # Chart for MCP server
└── messaging-gateway/# Chart for MCP server
```

Each chart should include:
- `Deployment` with resource requests/limits, probes, env vars
- `Service` for internal routing
- `ConfigMap` for non-sensitive config
- `HorizontalPodAutoscaler` for scale-out
- `PodDisruptionBudget` for HA

### Effect on the system
- Cannot deploy to Kubernetes
- No resource management, no auto-scaling, no rolling updates
- Production deployment is manual Docker run

### Priority: 🟠 High

---

## 21. Missing Docker Healthchecks

### Location
```
infra/docker-compose/docker-compose.yml — no healthcheck on any service
deploy/postgres/docker-compose.yml — postgres has healthcheck (the only one)
deploy/otel/docker-compose.yml — no healthchecks
```

### What exists now
Only Postgres has a `healthcheck` block. LiveKit, Redis, Qdrant, MinIO, OTel collector, 
and Prometheus all lack healthchecks. If a service fails, Docker has no way to detect it.

### What must be done

Add healthchecks to all compose services:
```yaml
redis:
  image: redis:7.4-alpine
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5

qdrant:
  image: qdrant/qdrant:v1.12.5
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
    interval: 10s
    timeout: 5s
    retries: 3

minio:
  image: minio/minio:...
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 10s
    timeout: 5s
    retries: 3
```

Also add `depends_on` with `condition: service_healthy` where appropriate.

### Effect on the system
- Docker Compose cannot detect or restart failed services
- A crashed Redis or Qdrant goes unnoticed until a caller hits an error
- Orchestrators (K8s, Nomad) rely on probes for pod management

### Priority: 🟡 Medium

---

## 22. Missing DB Backup & Restore Scripts

### Location
```
deploy/ — no scripts/ directory exists
no Makefile targets for backup or restore
```

### What exists now
No database backup or restore capability exists. The Postgres volume (`telecom_pgdata`) 
persists data, but there is no scheduled backup, no point-in-time recovery, no documented 
restore procedure.

### What must be built

Create `deploy/scripts/backup.sh`:
```bash
#!/bin/bash
# Usage: ./backup.sh [database] [output_dir]
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -h $PGHOST -U $PGUSER -d $PGDATABASE \
  --format=custom --file="${OUTPUT_DIR}/telecom_${TIMESTAMP}.dump"
echo "Backup written to ${OUTPUT_DIR}/telecom_${TIMESTAMP}.dump"
```

Create `deploy/scripts/restore.sh`:
```bash
#!/bin/bash
# Usage: ./restore.sh <backup_file>
pg_restore -h $PGHOST -U $PGUSER -d $PGDATABASE \
  --clean --if-exists --no-owner "$1"
```

Add Makefile targets:
```makefile
backup:
	./deploy/scripts/backup.sh
restore:
	./deploy/scripts/restore.sh $(BACKUP_FILE)
```

### Effect on the system
- Data loss from a failed migration or corruption is unrecoverable
- No compliance with §8.3 (retention/purge) without backup capability
- Disaster recovery time is effectively infinite

### Priority: 🟠 High

---

## 23. Missing Secrets Management

### Location
```
.env.example — contains all API key names but no values
apps/agent-worker/src/config/settings.py — reads from env
All services read credentials from environment variables
```

### What exists now
All secrets (API keys, passwords) come directly from environment variables. There is no 
vault, no encrypted secrets store, no secret rotation mechanism. The `.env` file contains 
everything in plaintext.

### What must be built

**Option A — HashiCorp Vault integration** (recommended for production):
```python
# packages/secrets/src/secrets/vault_client.py
import hvac

class VaultClient:
    def __init__(self, vault_addr: str, vault_token: str):
        self._client = hvac.Client(url=vault_addr, token=vault_token)
    
    def get_secret(self, path: str, key: str) -> str:
        return self._client.secrets.kv.v2.read_secret_version(path=path)["data"]["data"][key]
```

**Option B — Docker Secrets** (simpler):
```yaml
# docker-compose.yml
secrets:
  deepgram_api_key:
    file: ./secrets/deepgram_api_key.txt

services:
  agent-worker:
    secrets:
      - deepgram_api_key
```

**Minimum** — encrypt the `.env` file with `sops` or `git-crypt`.

### Effect on the system
- All secrets in plaintext in the `.env` file
- Any attacker with filesystem access gets all API keys
- Secret rotation requires manual process

### Priority: 🟠 High

---

## 24. Build Artifacts Committed to Repo

### Location
```
Root directory — *.zip files:
├── phase-8-changed-files.zip
├── phase-8-completion.zip
├── phase-9-changed-files.zip

Various — *.egg-info directories:
├── packages/*/src/*.egg-info/
├── services/*/src/*.egg-info/
├── apps/*/src/*.egg-info/
├── mcp-servers/*/src/*.egg-info/

Also: .venv/ committed in tree
```

### What exists now
ZIP archives of patch contents, build metadata directories (`.egg-info`), and the entire 
`.venv/` directory are checked into the repository.

### What must be done

1. **Remove** the ZIP files:
```bash
git rm phase-8-changed-files.zip phase-8-completion.zip phase-9-changed-files.zip
```

2. **Remove** all `.egg-info` directories (`.gitignore` already covers `*.egg-info/` but 
   existing ones must be removed with `git rm -r`)

3. **Remove** `.venv/` from the tree (also already in `.gitignore`)

4. **Clean up** `.gitignore` — add entries for `.zip` and ensure coverage:
```gitignore
# Add:
*.zip
*.tar.gz
*.7z
```

### Effect on the system
- Repository bloat: ZIP files and `.venv/` add megabytes of binary data
- Merge conflicts on `.egg-info` directories
- `.venv/` contains platform-specific binaries that don't work on other machines

### Priority: 🟡 Medium

---

## 25. No mypy Type Checking Configuration

### Location
```
Root — no mypy.ini, no pyproject.toml [tool.mypy] section
```

### What exists now
The entire project uses Python type hints extensively (`from __future__ import annotations`, 
`Mapped`, `list[str]`, etc.) but **never verifies them**. Type checking is aspirational — 
the annotations are never validated by mypy.

### What must be done

Create `mypy.ini` at root:
```ini
[mypy]
python_version = 3.12
strict = True
ignore_missing_imports = True
exclude = (.venv|patches|node_modules)
```

Alternatively, add to `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
exclude = [".venv", "patches", "node_modules"]
```

Add a Makefile target:
```makefile
typecheck:
	mypy apps/agent-worker/src services/context-service/src services/policy-service/src ...
```

### Effect on the system
- Type annotations provide no safety guarantees — bugs like `str` vs `UUID` pass silently
- Refactoring is riskier without type checking
- The comprehensive type hints in the persistence layer are never verified

### Priority: 🟡 Medium

---

## 26. No Ruff Linting Configuration in pyproject.toml

### Location
```
Root — Makefile runs ruff but no configuration file exists
Makefile Line 11: ruff check --fix . || true
pyproject.toml — no [tool.ruff] section
```

### What exists now
`make fmt` runs `ruff check --fix .` with default settings. No rules are configured, no 
line length is set, no `ignore` list exists. The `|| true` means failures are suppressed.

### What must be done

Add to root `pyproject.toml`:
```toml
[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
ignore = ["B904"]  # raise without from exception

[tool.ruff.format]
quote-style = "double"
```

Remove the `|| true` from the Makefile so lint failures fail CI.

### Effect on the system
- No consistent code style enforced
- Import sorting varies by developer
- Unused imports and variables go undetected
- Lint failures are silently ignored (`|| true`)

### Priority: 🟡 Medium

---

## 27. AccountServicesAgent Imports Wrong Base Class

### Location
```
apps/agent-worker/src/agents/account_services_agent.py
  Line 2: from livekit.agents import Agent
  (Should be: from agents.base_agent import BaseTelecomAgent)
```

### What exists now
The class inherits `Agent` (the raw LiveKit class) instead of `BaseTelecomAgent`. This 
means it misses:
- Automatic per-turn sentiment scoring
- Proactive de-escalation injection on frustration
- Escalation handling via the base hook
- Conversation turn recording

### What must be fixed

```python
from agents.base_agent import BaseTelecomAgent

class AccountServicesAgent(BaseTelecomAgent):
    ...
```

### Effect on the system
- If routed to AccountServicesAgent, frustrated callers don't get the de-escalation treatment
- The 5th persona is inconsistent with the other 4 (Triage, Billing, Technical, Manager)
- Sentiment data for calls handled by this agent is lost

### Priority: 🟡 Medium

---

## 28. Typo in Patches Directory Name

### Location
```
patches/persistance_p1/  ← "persistance" instead of "persistence"
patches/persistance_p2/
patches/persistance_p4/
patches/persistance_p5/
patches/persistance_p6/
patches/persistane_p3/   ← also misspelled differently! "persistane"
```

### What exists now
Six directories in `patches/` have misspelled names. The correct spelling is `persistence`.

### What must be done

Rename the directories globally:
```
patches/persistance_p1/  → patches/persistence_p1/
patches/persistance_p2/  → patches/persistence_p2/
patches/persistance_p4/  → patches/persistence_p4/
patches/persistance_p5/  → patches/persistence_p5/
patches/persistance_p6/  → patches/persistence_p6/
patches/persistane_p3/   → patches/persistence_p3/
```

### Effect on the system
- Cosmetic issue only — the patches are not part of the running code
- However, it looks unprofessional and makes navigation harder

### Priority: ⚪ Enhancement

---

## 29. Missing Database Migration Tests Automation

### Location
```
packages/persistence/ — alembic migrations exist but no automated test runs them
```

### What exists now
The Alembic migrations are well-structured (6 reversible migrations), but there is no 
automated test that:
1. Creates a temporary Postgres database
2. Runs `alembic upgrade head`
3. Runs the seed scripts
4. Runs `alembic downgrade -1` for each migration
5. Verifies the schema matches the model definitions

This means a schema change that breaks migration can go undetected.

### What must be built

Create `packages/persistence/tests/test_migrations.py`:
```python
"""Test that all migrations apply and roll back cleanly."""
import subprocess
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "alembic" / "versions"

def test_all_migrations_have_unique_revision_ids():
    """Every migration file has a unique revision ID."""
    revisions = []
    for f in sorted(MIGRATIONS_DIR.glob("*.py")):
        content = f.read_text()
        # Extract revision = "..." line
        ...
    assert len(revisions) == len(set(revisions))

def test_upgrade_head_does_not_raise():
    """alembic upgrade head completes without error against a real PG."""
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_downgrade_all_is_reversible():
    """Each migration's downgrade restores the previous state."""
    ...
```

### Effect on the system
- A bad migration can silently break the database
- No way to verify that the ORM models match the actual database schema
- Schema drift between environments goes undetected

### Priority: 🟡 Medium

---

## 30. Missing Production Dockerfiles for Services

### Location
```
apps/agent-worker/Dockerfile — exists (simple pip install)
services/*/ — no Dockerfiles exist
mcp-servers/*/ — no Dockerfiles exist
apps/business-api/ — no Dockerfile
apps/token-service/ — no Dockerfile
```

### What exists now
Only `apps/agent-worker/Dockerfile` exists. All other services lack Dockerfiles, meaning 
they must be run with `pip install -e . && uvicorn ...` manually.

### What must be built

Create `Dockerfile` for each deployable service (template):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY src ./src
CMD ["uvicorn", "package.main:app", "--host", "0.0.0.0", "--port", "8101"]
```

Services needing Dockerfiles:
- `services/context-service/`
- `services/decision-service/`
- `services/policy-service/`
- `services/execution-service/`
- `services/knowledge-service/`
- `services/notification-service/`
- `apps/business-api/`
- `apps/token-service/`
- `mcp-servers/ticketing-glpi/`
- `mcp-servers/ai-knowledge-rag/`
- `mcp-servers/messaging-gateway/` (after creation)

### Effect on the system
- Cannot containerize or deploy most services
- No consistent base image, no vulnerability scanning
- Developer environment and production diverge

### Priority: 🟠 High

---

## 31. Dead Test in Resilience Suite

### Location
```
apps/agent-worker/tests/resilience/test_chaos_wiring.py
  Line 30: assert LANGUAGE_PRESETS["ar"]["deepgram_language"] == "ar"
```

### What exists now
This test expects a key `deepgram_language` in `LANGUAGE_PRESETS["ar"]`, but the actual 
`language_presets.py` defines only `stt_language` and `tts_voice`. The test was written 
against an older spec and never updated. It fails on every run.

### What must be fixed

Change the test to use the correct key:
```python
# Line 30:
assert LANGUAGE_PRESETS["ar"]["stt_language"] == "ar"
```

Or remove the test entirely if it's no longer relevant.

### Effect on the system
- CI pipeline has a permanent red test
- Developers learn to ignore test failures
- Real issues get buried under the noise

### Priority: 🟡 Medium

---

## Summary Table

| # | Component | Location | Priority |
|---|---|---|---|
| 1 | Empty OSS schema | `persistence/models/oss.py` — doesn't exist | 🟠 High |
| 2 | Empty Provisioning schema | `persistence/models/provisioning.py` — doesn't exist | 🟠 High |
| 3 | Empty MCP server | `mcp-servers/messaging-gateway/` — no files | 🟠 High |
| 4 | Stub adapters (6) | `packages/integration-adapters/` — all NotImplementedError | 🔴 Critical |
| 5 | Mock GLPI client | `mcp-servers/ticketing-glpi/adapters/glpi_client.py` | 🔴 Critical |
| 6 | Mock SMS/Email/WhatsApp | `services/notification-service/channels.py` | 🔴 Critical |
| 7 | No Qdrant vector search | `services/knowledge-service/retriever.py` — lexical only | 🟠 High |
| 8 | No Redis caching | All services — env var exists, no code | 🟠 High |
| 9 | No MinIO storage | `agent-worker/src/` — no upload code | 🟠 High |
| 10 | AccountServicesAgent stub | `apps/agent-worker/src/agents/account_services_agent.py` | 🟠 High |
| 11 | Mock dispatch | `services/execution-service/executor.py` — generates fake refs | 🔴 Critical |
| 12 | Notification-client stub | `packages/notification-client/client.py` — logs only | 🟠 High |
| 13 | Dead code | `context-service/mock_directory.py` + `aggregator.py` | 🟡 Medium |
| 14 | No connection pool config | `packages/persistence/engine.py` | 🟡 Medium |
| 15 | Missing JSONB GIN indexes | Various model files | 🟡 Medium |
| 16 | **CORS wide open** | `apps/token-service/main.py` `allow_origins=["*"]` | 🔴 Critical |
| 17 | **Default credentials** | `docker-compose.yml`, `.env.example` | 🔴 Critical |
| 18 | **No service auth** | All clients — no X-API-Key header | 🔴 Critical |
| 19 | No API gateway | `infra/` | 🟠 High |
| 20 | No CI/CD | `infra/ci-cd/` — README only | 🟠 High |
| 21 | No Helm charts | `infra/helm/` — README only | 🟠 High |
| 22 | No Docker healthchecks | `docker-compose.yml` | 🟡 Medium |
| 23 | No DB backup scripts | `deploy/scripts/` — doesn't exist | 🟠 High |
| 24 | No secrets management | Environment variables only | 🟠 High |
| 25 | Build artifacts in repo | ZIP files, `.egg-info`, `.venv` | 🟡 Medium |
| 26 | No mypy config | Root — no config file | 🟡 Medium |
| 27 | No ruff config | `pyproject.toml` — no `[tool.ruff]` | 🟡 Medium |
| 28 | Wrong base class | `account_services_agent.py` imports `Agent` not `BaseTelecomAgent` | 🟡 Medium |
| 29 | Typo in patches dir | `patches/persistance_*` | ⚪ Enhancement |
| 30 | No migration tests | `packages/persistence/tests/` | 🟡 Medium |
| 31 | Missing Dockerfiles | Services have no Dockerfiles | 🟠 High |
| 32 | Dead test | `test_chaos_wiring.py:30` KeyError | 🟡 Medium |

### 🔴 Critical (must fix before any production deployment): 6 items
### 🟠 High (blocks feature completeness or operations): 11 items
### 🟡 Medium (quality, maintainability, or performance): 11 items
### ⚪ Enhancement (cosmetic or organizational): 1 item

---

## Implementation Order

### Sprint 1 (Weeks 1–2): Security & Infrastructure
1. Close CORS wildcard → `token-service/main.py`
2. Remove default credentials → `docker-compose.yml`, `.env.example`
3. Add service-to-service auth → all clients + all FastAPI apps
4. Add Docker healthchecks → `docker-compose.yml`
5. Clean up build artifacts → `.gitignore`, `git rm`
6. Add mypy + ruff config → `pyproject.toml`

### Sprint 2 (Weeks 3–5): Core Adapters
7. Implement GLPI REST client → `ticketing-glpi/adapters/glpi_client.py`
8. Implement SMS/WhatsApp/Email channels → `notification-service/channels.py`
9. Implement integration adapters (OCS, billing, payment, CRM) → `integration-adapters/`
10. Replace mock dispatch → `execution-service/executor.py`
11. Implement notification-client → `notification-client/client.py`

### Sprint 3 (Weeks 5–7): Storage & Caching
12. Implement Redis caching → `packages/cache/`
13. Implement MinIO audio storage → `agent-worker/src/storage/`
14. Implement Qdrant vector search → `knowledge-service/indexer.py` + retriever

### Sprint 4 (Weeks 7–9): Remaining Schemas & Components
15. Create OSS schema tables → `persistence/models/oss.py`
16. Create Provisioning schema tables → `persistence/models/provisioning.py`
17. Create messaging-gateway MCP server → `mcp-servers/messaging-gateway/`
18. Implement AccountServicesAgent → `agent-worker/agents/account_services_agent.py`

### Sprint 5 (Weeks 9–11): Operations & Deployment
19. Create Dockerfiles for all services
20. Create Helm charts for all services
21. Create DB backup/restore scripts
22. Create CI/CD pipeline (GitHub Actions)
23. Implement secrets management (Vault or Docker Secrets)

### Sprint 6 (Weeks 11–12): Hardening
24. Add GIN indexes → migration 0008
25. Add connection pool config → `persistence/engine.py`
26. Remove dead code → `mock_directory.py`, `aggregator.py`
27. Fix dead test → `test_chaos_wiring.py`
28. Fix typo in patches directory

---