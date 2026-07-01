# Phase 9 — Ticketing & Notifications

**Goal:** close the loop — open follow-up tickets and send written confirmations.
**Exit criterion:** a call needing follow-up creates a ticket and the caller gets a written
confirmation; a ticket can be resolved.

**22 files, no deletions.** Boundary clean; everything compiles; notification tests pass; GLPI
lifecycle verified. Also delivers review **note 2** (`resolve_ticket`).

## What's in it

### ticketing-glpi MCP server (`mcp-servers/ticketing-glpi/`, port 8202)
Its own MCP server (review note 1), separate from knowledge.
- `adapters/glpi_client.py` — `MockGlpiClient` (in-memory tickets); a real GLPI REST adapter
  replaces it later, tools unchanged.
- `tools/glpi_ticket_ops.py` — `create_ticket`, `get_ticket_status`, **`resolve_ticket`** (note 2),
  `lookup_tickets`. `create_ticket` also calls the notification-service to text the caller a
  written confirmation (native GLPI behaviour → guarantees the loop closes).
- `server.py` — FastMCP streamable-HTTP, serves `/mcp`.

### notification-service (`services/notification-service/`, port 8106)
- `channels.py` — `NotificationChannel` interface + mock SMS/WhatsApp/Email senders (PII-masked).
- `templates.py` — localized templates (fr/ar/en): `ticket_created`, `callback_scheduled`.
- `main.py` — `POST /notify`, `GET /sent` (inspection), `GET /health`.

### Worker integration
- `mcp_clients/ticketing_toolset.py` — scoped `MCPToolset` over ticketing-glpi (allow-list).
- `clients/notification_client.py` — worker-initiated confirmations (degrades gracefully).
- `tasks/callback_schedule_task.py` — now sends a **written confirmation** on a recorded callback,
  closing the Phase 8 "callback with written confirmation" gap.
- `agents/technical_agent.py` + `agents/manager_agent.py` — gain the ticketing toolset; both keep
  `BaseTelecomAgent`.
- `config/settings.py` — adds `TICKETING_MCP_URL` (default `http://localhost:8202/mcp`).

## Apply & run
Unzip at repo root. Two new processes:
```bash
cd services/notification-service && pip install -e . && uvicorn notification_service.main:app --port 8106
cd mcp-servers/ticketing-glpi    && pip install -e . && python -m ticketing_glpi.server   # :8202/mcp
```
The MCP server reads `NOTIFICATION_SERVICE_URL` to send the ticket confirmation. Docker DNS:
`NOTIFICATION_SERVICE_URL=http://notification-service:8106`, `TICKETING_MCP_URL=http://ticketing-glpi:8202/mcp`.

## Proving the exit criterion
- **Ticket + written confirmation:** route to technical, describe an unsolvable issue → `create_ticket`
  returns `GLPI-00001` with `written_confirmation_sent: true`; `curl http://localhost:8106/sent` shows the SMS.
- **Resolve (note 2):** issue solved on the call → `resolve_ticket` → status `resolved`.
- **Callback confirmation (closes Phase 8):** escalate with no advisor → `callback_scheduled` appears in `/sent`.
- **Offline tests:** `cd services/notification-service && PYTHONPATH="src:../../packages/pii-shield/src" python -m pytest -q tests/` → 3 passed.

## Honest scope notes
- **Tickets & notifications are mock** — real GLPI REST + real SMS/Email providers drop in behind the
  same interfaces; tickets move to Postgres/GLPI in the persistence phase.
- **Contact resolution:** the mock notifier "sends" to the `customer_id`; production resolves the real
  MSISDN/email before sending.
- **messaging-gateway** stays a placeholder — sending is owned by this notification-service, not MCP.

**Traceability:** CDC §4.8 → ticketing-glpi MCP; §4.10 → notification-service; review note 1 → MCP
split; review note 2 → `resolve_ticket`. **Next:** Phase 10 — Frontend (token-service + client widget).
