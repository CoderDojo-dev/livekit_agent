# version_44 — Ticketing Live-Only Hardening + Honest Failure Propagation

## What Changed

### MockGlpiClient Removed / Live-Only Ticketing
`MockGlpiClient` (the in-memory twin) and the `CONNECTOR_MODE` env var are **removed**. The ticketing subsystem now only runs against a real GLPI. `get_glpi_client()` returns `LiveGlpiClient` directly and raises `GlpiConfigError` if `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, or `GLPI_USER_TOKEN` are missing — no silent fallback to mock. The three GLPI settings are now **required** for the ticketing-glpi service to start.

`.env.example` updated: comments now state "Ticketing is LIVE-ONLY: these three are REQUIRED for the ticketing-glpi service to start (independent of CONNECTOR_MODE)."

### Lazy GLPI Client Initialization
`glpi_ticket_ops.py` now uses a `_glpi()` lazy factory function instead of importing `_client = get_glpi_client()` at module level. This means the module imports even before GLPI env vars are loaded — the `/health` route and tests work without a live GLPI. The first ticket operation triggers lazy validation and raises `GlpiConfigError` if GLPI is not configured.

### Honest Failure Propagation (`TicketingUnavailable`)
New `TicketingUnavailable` exception in `ticket_tools.py`. All five MCP call wrappers (`create_support_ticket`, `check_customer_tickets`, `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`) now catch transport/protocol errors (connection refused, timeout, protocol error) and return a structured response:

```json
{"outcome": "unavailable", "message": "The ticketing system is unavailable right now. ... Do NOT invent a ticket, a reference, or a status."}
```

A shared `_unavailable()` helper ensures consistency. Raw exceptions no longer crash the tool call and leave the agent silent.

### Agent Persona Instruction Updates
**manager_agent.py**: Instructions softened — ticketing is "optional and only when it helps". Added "if a ticket tool returns 'unavailable', say honestly you cannot reach the ticketing system right now."

**technical_agent.py**: Instructions rewritten — ticketing is "not something you bring up on every call". Explicit bullet-point guidance: when to check existing tickets, when to create one, when to resolve, and crucially: "If a ticket tool result is 'unavailable', tell the caller honestly ... never pretend it worked."

## No Container / SDK Changes
No Dockerfile, docker-compose, or library version changes in this version.

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/glpi_client.py` | MODIFIED | Removed MockGlpiClient + CONNECTOR_MODE; get_glpi_client() now live-only |
| `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` | MODIFIED | Lazy _glpi() factory instead of module-level import |
| `apps/agent-worker/src/tools/ticket_tools.py` | MODIFIED | TicketingUnavailable exception + _unavailable() helper on all wrappers |
| `apps/agent-worker/src/agents/manager_agent.py` | MODIFIED | Softened ticketing instructions; honest failure reporting |
| `apps/agent-worker/src/agents/technical_agent.py` | MODIFIED | Rewritten ticketing instructions; honest failure reporting |
| `.env.example` | MODIFIED | GLPI settings now REQUIRED; CONNECTOR_MODE removed |
