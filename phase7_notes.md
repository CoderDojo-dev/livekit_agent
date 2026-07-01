# Phase 7 Deployment Results & Review Notes

## 1. Actual Results Achieved in Phase 7
The recent application of the Phase 7 patch and the cleanup of legacy modules have successfully implemented the concept of **Idempotent Execution and Sensitive Actions**. The following architectural capabilities are now live in the codebase:

*   **Idempotent Execution Service (`services/execution-service`)**:
    *   Fully functional backend wrapper running on port `8105`.
    *   Prevents duplicate sensitive actions from executing twice (e.g., locking concurrent API calls via `idempotency_key`).
    *   Generates a standardized reference `(e.g., PAY-..., SIM-..., DEF-...)`.
*   **Consent Registration Workflow (`tasks/consent_task.py`)**:
    *   Replaced the empty class with actual Phase-3 promised logic. The Triage Agent strictly gates conversations with a legal consent prompt before initiating any telecom business logic.
*   **PII Masking Filter (`packages/pii-shield`)**:
    *   Log instances successfully omit direct exposure of customer names and MSISDN numbers, opting to trace only via standard `customer_id` across logging mechanisms.
*   **Decoupled MCP Providers (`mcp-servers/`)**:
    *   `knowledge-glpi-mcp` is removed.
    *   A clean boundary exists: `ai-knowledge-rag` now purely handles FAQs and corpus queries, while the scaffold for `ticketing-glpi` sits independently for future API integration (slated for Phase 9).
*   **Technical Pipeline Routing**:
    *   Extended `tools/routing_tools.py` successfully allowing intent navigation beyond just Billing; `TechnicalAgent` handles the `unblock_sim` flow natively.

---

## 2. Remarques & Ambiguities

As a reviewer analyzing the implementation up to Phase 7, here are critical observations for upcoming sprints:

### 1. Persistence Layer Discrepancy (Phase 7.5 Transition)
*   **Current State:** Execution services currently commit idempotency and action outcomes strictly to the ephemeral in-memory state. `mock_directory` persists within the application instances across REST domains.
*   **Ambiguity:** Because of how LiveKit handles sudden disconnections (network dropping on the customer’s phone), if a sensitive action *(like Unblock SIM)* triggers right as a socket drops, the memory-bound state might fall out of sync with an eventual re-connect request if the containers recycle.
*   **Solution Needed:** The planned **Phase 7.5 Persistence Integration** (migrating everything to permanent PostgreSQL schemas) must be executed immmediately next, as delayed execution tracking can result in financial audit errors on a telecom production level.

### 2. Ambiguity in "Consent Task" Fallbacks
*   **Current State:** The Triage Agent explicitly halts to get consent. 
*   **Observation/Ambiguity:** What exactly happens if the user outright says "No"? Is the call completely terminated via `hangup_tool` immediately, or does the Agent offer a fallback standard compliance routing (such as routing them to an IVR machine where voice AI is bypassed)? The current business logic ruleset in `triage_agent.py` implies it stops, but a graceful termination script or explicit handoff seems opaque in the source definitions. 

### 3. Messaging Gateway Constraints (As an MCP vs Domain Service)
*   **Observation:** The scaffold for `mcp-servers/messaging-gateway` currently exists.
*   **Concern:** As noted in the `PHASE-7-README`, sending SMS/Emails should technically not be wrapped inside a generic MCP tool because LLMs are prone to hallucinating arguments, and it is a *sensitive outbound business action*. It should strongly be pushed deeply inside a standard Domain API (`notification-service`). Keeping it as an MCP risks the LLM dispatching random SMS messages to clients unprompted during "creativity spikes."

### 4. Overlap on Context State (Redis vs Postgres)
*   **Ambiguity:** According to the `.env`, both Redis and Postgres are heavily active. But defining the exact boundary of what enters the *Session State* inside Redis vs what resides formally in the Postgres CRM will determine how long Agent-User contextual "memory" lasts if a caller hangs up and calls back 3 months later. A strict architecture principle is required during Phase 7.5 to determine where state persistence technically expires.
