# version_45 — Customer-to-GLPI User Mapping (Requester Identity)

## What This Solves
Every ticket needs a GLPI "requester" (user) so it is searchable by `list_for(requester_glpi_id)`. Previously `requester_glpi_id` was either absent (tickets filed under no user) or guessed by the model. This version creates a **permanent, persisted link** between a telecom customer and their GLPI user — set once when the customer is created (or backfilled for existing customers), then auto-injected on every ticket operation.

## Container / SDK Changes
**No container or SDK version changes** in this version — purely data model, service logic, and MCP tools.

## DB Migration (alembic)
**`0011_customer_glpi_user.py`** — adds `glpi_user_id` (Integer, unique, indexed) to the `crm.customers` table. The unique constraint ensures no two customers share a GLPI user (each telecom customer gets their own GLPI requester account). Idempotent.

## CRM Model
**`Customer.glpi_user_id`** (`Mapped[int | None]`) on `packages/persistence/src/persistence/models/crm.py` — the permanent customer↔GLPI-user link. Nullable: existing customers start at NULL and are backfilled; new customers get it set at creation.

## GLPI Client — New `ensure_user()`
`LiveGlpiClient.ensure_user(login, first_name, last_name, email) -> int | None`:
- Searches GLPI User by login name (field 1)
- Returns existing id on match (idempotent)
- Creates a new GLPI User via `POST /User` on miss, optionally setting firstname/realname/email
- Returns the GLPI user id, or None on failure

## Mirror — New CRUD for GLPI User Mapping
Three new functions in `mirror.py`:
- **`read_glpi_user_id(customer_id)`** — reads the stored GLPI user id from `crm.customers`
- **`write_glpi_user_id(customer_id, glpi_user_id)`** — persists the mapping after GLPI user creation
- **`customers_without_glpi_user()`** — returns all active customers missing the mapping (for backfill)

## MCP Tools
### New: `ensure_customer_glpi_user`
Exposed as an MCP tool and as a console script (`ticketing-glpi-backfill-users`):
- Idempotent: if the mapping already exists, returns it unchanged
- Otherwise: calls `_glpi().ensure_user()` to find-or-create the GLPI requester, then writes the id to the mirror
- Returns `{"customer_id", "glpi_user_id", "created": bool}`

### Auto-Resolution in `create_ticket` and `lookup_tickets`
Both tools now call `mirror.read_glpi_user_id(customer_id)` when `requester_glpi_id` is not provided, so tickets are always filed under a real GLPI user even when the agent doesn't pass the id explicitly.

### Console Script: `ticketing-glpi-backfill-users`
Registered in `pyproject.toml` as `ticketing-glpi-backfill-users`. Iterates all active customers without a mapping, creates their GLPI user, and persists the id. Run any time to backfill existing customers.

## Agent Worker — Identity Injection
- **`customer_context.py`**: new `glpi_user_id: int | None` field on `CustomerContext`
- **`ticket_tools.py`**: `create_support_ticket` and `check_customer_tickets` now pass `requester_glpi_id` from the customer context, so every ticket operation carries the verified GLPI user id
- **`Customer360` schema** (`schemas.py`): new `glpi_user_id` field
- **`CrmRepository`** (`repositories.py`): reads `customer.glpi_user_id` from the DB and includes it in the response

## Full Data Flow
1. Customer created (or backfill runs) → `ensure_customer_glpi_user` finds-or-creates GLPI user → id stored in `crm.customers.glpi_user_id`
2. Caller rings → context-service loads `Customer360` → `CustomerContext.glpi_user_id` populated → distributed to agent-worker
3. Agent calls `check_customer_tickets` or `create_support_ticket` → `requester_glpi_id` injected from context → MCP tools auto-resolve from mirror → tickets filed under a real GLPI user → searchable by requester id

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `packages/persistence/alembic/versions/0011_customer_glpi_user.py` | NEW | Add glpi_user_id to crm.customers |
| `packages/persistence/src/persistence/models/crm.py` | MODIFIED | Customer.glpi_user_id column |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/glpi_client.py` | MODIFIED | ensure_user() — search/create GLPI user |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/mirror.py` | MODIFIED | read/write/query glpi_user_id functions |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` | MODIFIED | ensure_customer_glpi_user tool + backfill script + auto-resolve |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/server.py` | MODIFIED | expose ensure_customer_glpi_user tool |
| `mcp-servers/ticketing-glpi/pyproject.toml` | MODIFIED | ticketing-glpi-backfill-users script entry |
| `apps/agent-worker/src/session/customer_context.py` | MODIFIED | glpi_user_id field |
| `apps/agent-worker/src/tools/ticket_tools.py` | MODIFIED | Pass requester_glpi_id from context |
| `services/context-service/src/context_service/schemas.py` | MODIFIED | glpi_user_id on Customer360 |
| `services/context-service/src/context_service/repositories.py` | MODIFIED | Read glpi_user_id from DB |
