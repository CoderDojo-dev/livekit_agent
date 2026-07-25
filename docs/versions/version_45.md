# Version 45 — Customer-to-GLPI User Mapping (Requester Identity)

## What's new
- **Migration 0011_customer_glpi_user**: adds `glpi_user_id` (Integer, unique, indexed) to `crm.customers`
- **GLPI client `ensure_user()`**: search User by login, create on miss, return GLPI user id (idempotent)
- **Mirror layer**: `read_glpi_user_id`, `write_glpi_user_id`, `customers_without_glpi_user` for persisting and querying the mapping
- **MCP tools**: `ensure_customer_glpi_user` (find-or-create + persist); `backfill_glpi_users` console script; `create_ticket`/`lookup_tickets` auto-resolve `requester_glpi_id` from the mirror
- **Agent tools**: `create_support_ticket`/`check_customer_tickets` pass `glpi_user_id` from `CustomerContext`
- **CRM model**: `Customer.glpi_user_id` (Mapped[int | None])
