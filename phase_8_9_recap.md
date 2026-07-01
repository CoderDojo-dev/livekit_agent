# Phases 8 & 9 Technical Recap

## 1. Technical Changes & Updates

### Phase 8 Updates (Sentiment, Handoff & Escalation)
This phase shifted the AI from executing blindly to becoming actively aware of user frustration and managing non-technical fallback routes.
*   **BaseTelecomAgent Framework:** Centralized all persona types (Triage, Billing, Technical, Manager) to inherit from a unified `BaseTelecomAgent`. This base layer monitors call-turn lifecycle events passively.
*   **Deterministic Sentiment Engine (`sentiment_scorer.py`):** Scores user telemetry (like aggressive phrasing) purely via localized lexical dictionaries in French/English/Arabic, reducing heavy LLM latency while still capturing frustration signatures immediately.
*   **Proactive De-Escalation:** When `consecutive_negative_turns` hits thresholds (2+), an automated underlying system prompt is injected into context forcing the AI to explicitly empathize and offer a human escalation rather than repeating script logic.
*   **Clarification Loops (`clarification_tools`):** Ambiguity is now bounded. If an agent tries to clarify a customer's query twice without success, it triggers mandatory fallback routing via `request_clarification` to prevent infinite AI loops.
*   **SIP Transfer & Callbacks (`sip_transfer.py`):** If a user requires a human, the `ManagerAgent` dynamically searches via `routing_client.py` for a live SIP extension. If none exist (or transfer fails), a deterministic `CallbackScheduleTask` catches the call natively.

### Phase 9 Updates (Ticketing & Notifications)
This phase closed out the post-call execution loop, ensuring AI actions manifest into real-world operational markers and notifications.
*   **Segmented Ticketing MCP (`mcp-servers/ticketing-glpi`):** Deprecated the merged GLPI/Knowledge server. The Ticketing server is now standalone on port `8202` maintaining `create_ticket`, `get_ticket_status`, and securely implementing `resolve_ticket`.
*   **Notification Domain Engine (`services/notification-service`):** Operates on port `8106` providing isolated outbound multi-channel pipelines (SMS/WhatsApp/Email) protected by PII shields.
*   **Closing Functional Gaps:** The Callback structure laid out in Phase 8 was officially chained into the Notification service. The moment a callback is scheduled, an outbound confirmation SMS is mocked up in the backend tracking. GLPI ticket generation also fires SMS receipt bindings concurrently.

---

## 2. Still Missing & Upcoming Needs

While the core decisioning, NLP routing, and action layers are extremely robust, several enterprise gaps remain scheduled for the upcoming phases:

### A. Persistence Migration (Phase 7.5 Roadmap)
*   **Mock State vs Permanent State:** The `services/context-service` heavily leans on `mock_directory.py` and volatile local lists. The Execution and Session limits currently expire in ephemeral memory (Redis).
*   **Missing Postgres Schemas & Validations:** The full Postgres CRM schema needs structuring. Without formal CRM database integrations, critical operations (like verifying standard National ID / CIN parameters as required by the LLM prompts) remain disjointed.

### B. Front-End Interaction Layers (Phase 10)
*   **The WebSocket Client (`apps/client-widget`):** Currently, all voice interactions seem tested over back-channel execution parameters or command line wrappers. The formal React frontend harnessing `@livekit/components-react` needs deployment to expose simple 1-click browser communication pathways.
*   **Token Authentication (`token-service`):** LiveKit relies on signed authorization tokens required to dictate connection rules dynamically to incoming users calling into the web interface. 

### C. Live Production System Bindings
*   **True Provider API Adapters:** Real OCS (Online Charging System), Telecom Billing API endpoints, and production SMS gateway URLs (e.g. Twilio/Infobip) need to replace the local class mocks located across `execution-service` and `notification-service`.
