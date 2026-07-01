# ticketing-glpi (MCP server) — built in Phase 9

Transactional GLPI ticket operations, decoupled from knowledge (review note 1).

Planned tools (Phase 9 — Ticketing & Notifications):
- `create_ticket(subject, body, priority)`
- `get_ticket_status(ticket_id)`
- `resolve_ticket(ticket_id, resolution)`  ← review note 2 (close the dossier)
- `lookup_tickets(customer_id)`

Runs as its own streamable-HTTP MCP server on a distinct port (e.g. 8202), consumed by the
agent via a scoped `MCPToolset` with its own `allowed_tools` allow-list. Ticket *resolution*
is a low-risk write and is acceptable behind MCP; anything account-bound stays a local tool.