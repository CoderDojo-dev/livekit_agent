# messaging-gateway — deferred to Phase 9 (see note)

Requested in review note 1 for future SMS/Email tools.

**Architectural caution:** sending SMS/WhatsApp/Email is a *sensitive outbound side-effect*.
The blueprint assigns it to the `notification-service` (a domain service), not to an MCP
server. Recommendation: keep sending in `services/notification-service/` (Phase 9). Only
introduce a `messaging-gateway` MCP server if a second channel (e.g. an internal tool or
text chatbot) needs to *reuse* the same send capability — the one criterion the blueprint
uses to justify placing something behind MCP. This folder is a placeholder pending that
decision in Phase 9.