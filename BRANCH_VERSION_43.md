# version_43 — Full GLPI REST Integration + Identity-Injecting Agent Ticket Tools

## Container / Infra Changes
- **New container: `glpi` + `glpi-db`** (`infra/docker-compose/docker-compose.glpi.yml`)
  - Local GLPI 10.0.15 stack (diouxx/glpi image) with MariaDB 10.11
  - Persistent volumes for DB data and app data
  - Healthcheck on the DB; opt-in via `-f docker-compose.glpi.yml`
- **New named volume: `glpi-db-data`, `glpi-app-data`** for persistent GLPI state
- **`docker-compose.apps.yml`** — added GLPI connectivity env vars to ticketing-glpi service:
  `CONNECTOR_MODE`, `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`
- **`TICKETING_HTTP_URL`** env var added to agent-worker for direct HTTP calls to ticketing MCP

## SDK / Library Version Changes
- **`mcp`**: bumped from `>=1.0.0` to `>=1.24` — required for streamable HTTP client + structured content
- **`observability-kit`**: new dependency — enables distributed trace context injection on every outbound GLPI REST call (`inject_trace_context`)

## GLPI Ticketing MCP Server (ticketing-glpi) — Full Rewrite

### LiveGlpiClient — Full CRUD over GLPI REST API
The mock-only client is replaced by a proper REST client (`mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/glpi_client.py`):
- `create(customer_id, subject, description, category, priority, requester_glpi_id)` — opens a ticket via `POST /Ticket`
- `get(ticket_id)` — reads one ticket via `GET /Ticket/<id>`, maps numeric status to vocabulary
- `update(ticket_id, subject, description, priority, status)` — `PUT /Ticket/<id>`
- `resolve(ticket_id, resolution)` — sets GLPI status=5 (solved) + solution
- `close(ticket_id)` — sets GLPI status=6 (closed)
- `delete(ticket_id)` — `DELETE /Ticket/<id>?force_purge=true`
- `list_for(requester_glpi_id)` — `GET /search/Ticket` with field-4 (requester) criteria, returns tickets with numeric field mapping
- Session management: `initSession` → App-Token + user_token auth → `killSession` after every call
- **Trace context**: every outbound call carries distributed trace headers via `observability_kit.telemetry.inject_trace_context()`
- **`GlpiConfigError`**: when `CONNECTOR_MODE=live` but GLPI credentials are missing, raises loud error instead of silently falling back to mock

### Postgres Mirror — Full Sync Layer
The mirror (`mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/mirror.py`) now supports:
- `mirror_update()` — partial field update (subject, category, priority, status)
- `mirror_set_status()` — set status only (used by resolve/close)
- `mirror_delete()` — remove a row, returns bool
- `upsert_from_glpi()` — insert or refresh from GLPI data (reflects admin-side changes into local view)
- `read_for_customer()` now returns full row dict (all fields) ordered by `created_at DESC`
- `_row_to_dict()` — shapes Ticket row for agent/UI consumption (ticket_id, status, subject, category, priority, customer_id, subscription_id, created_at, last_synced_at)

### MCP Tools — Full Lifecycle
Exposed MCP tools now include: `create_ticket`, `get_ticket_status`, `update_ticket`, `resolve_ticket`, `close_ticket`, `delete_ticket`, `lookup_tickets`.

Pattern: **GLPI-first-write, then mirror** — every write goes to GLPI first, then the mirror is updated. Reads prefer the mirror (fast, local) and reconcile from GLPI when cold (via `upsert_from_glpi`), ensuring an admin's GLPI-side status change is visible on the voice path.

### Health Endpoint
New `GET /health` custom route on the MCP server returns `{"status": "ok", "service": "ticketing-glpi", "connector_mode": "live|mock"}` for Docker/K8s liveness probes.

## Agent Worker — Identity-Injecting Ticket Tools

### New `ticket_tools.py` (`apps/agent-worker/src/tools/ticket_tools.py`)
Agent-side wrappers that inject **verified identity** (customer_id, subscription_id) from `RunContext.session.userdata.customer_context`:
- `create_support_ticket(subject, description, category, priority)` — model supplies human content, platform injects identity + language, calls MCP's `create_ticket`
- `check_customer_tickets()` — lists caller's tickets with open/resolved counts; returns a `message` instructing the agent to summarize in the caller's language
- `get_ticket_state(ticket_id)` — check one ticket's status
- `mark_ticket_resolved(ticket_id, resolution)` — resolve when solved on the call
- `update_support_ticket(ticket_id, subject, description, priority, category)` — amend a ticket

### Manager Agent (`manager_agent.py`)
- Replaced `build_ticketing_toolset()` with individual tools: `create_support_ticket`, `check_customer_tickets`, `get_ticket_state`
- Updated instructions: "To see the caller's existing tickets call `check_customer_tickets`; if the issue needs tracking and none covers it, call `create_support_ticket`"

### Technical Agent (`technical_agent.py`)
- Replaced `build_ticketing_toolset()` with individual tools: `create_support_ticket`, `check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`
- Updated instructions: proactive — "FIRST call `check_customer_tickets`: if an open ticket already covers it, reassure them; if resolved, tell them the good news; if no ticket covers it, call `create_support_ticket`"

## Config Files
- **`settings.py`** — added `TICKETING_HTTP_URL` (default `http://localhost:8202`)
- **`.env.example`** — added GLPI local stack env vars: `GLPI_DB_ROOT_PASSWORD`, `GLPI_DB_NAME`, `GLPI_DB_USER`, `GLPI_DB_PASSWORD`, `GLPI_TIMEZONE`

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/glpi_client.py` | MODIFIED | Full GLPI REST CRUD + trace context + GlpiConfigError |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/mirror.py` | MODIFIED | update/delete/upsert operations; full row shaping |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` | MODIFIED | update/close/delete tools; GLPI-first-write pattern |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/server.py` | MODIFIED | New tools + /health endpoint |
| `mcp-servers/ticketing-glpi/pyproject.toml` | MODIFIED | mcp >=1.24, +observability-kit |
| `apps/agent-worker/src/tools/ticket_tools.py` | NEW | Identity-injecting agent-side ticket wrappers |
| `apps/agent-worker/src/agents/technical_agent.py` | MODIFIED | Replaced ticketing toolset; proactive ticket check instructions |
| `apps/agent-worker/src/agents/manager_agent.py` | MODIFIED | Replaced ticketing toolset; updated instructions |
| `apps/agent-worker/src/config/settings.py` | MODIFIED | Added TICKETING_HTTP_URL |
| `infra/docker-compose/docker-compose.glpi.yml` | NEW | Local GLPI 10.0.15 + MariaDB stack |
| `infra/docker-compose/docker-compose.apps.yml` | MODIFIED | GLPI env vars + TICKETING_HTTP_URL |
| `.env.example` | MODIFIED | GLPI local stack env vars |
