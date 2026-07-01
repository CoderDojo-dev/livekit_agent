**Context:** Telecom AI Platform (Phases Review)  
**Priority:** High (Addressing Architectural Scalability & Data Integrity)

---

ive implment phases and here is my last honest review
### 1. MCP Architecture: Domain Decoupling & Scalability
Current structure is confusing: `mcp-servers\knowledge-glpi-mcp\src\knowledge_glpi_mcp`.  
**Issue:** Combining **Knowledge RAG** (FAQ/Static data) with **GLPI** (Transactional Ticketing) under one folder is unprofessional and limits scalability.  
**Requirement:** 
- Every toolset should be unique. Separate them into individual, clean folders:
    - `/mcp-servers/ticketing-glpi/`
    - `/mcp-servers/ai-knowledge-rag/`
    - `/mcp-servers/messaging-gateway/` (For future SMS/Email tools)
- This is a "clean code" mandatory requirement for a professional-grade platform.

### 2. GLPI Lifecycle Completeness
**Issue:** Current tools only support `create_ticket` and `get_status`.  
**Requirement:** Implement `delete_ticket` or `resolve_ticket`. If a user’s problem is solved during a call or through a manual check, the Agent must have the power to clear the dossier. A "one-way" ticketing system is technically incomplete.

### 3. Production Data & Postgres Migration
**Issue:** The project relies on `mock_directory.py` and local lists.  
**Requirement:** 
- Delete all mock data scripts at the end of this phase.
- All persistent data (Customers, Usage, Tickets) **must** reside in the dedicated **Postgres container**.
- Services must interface with these databases through their specific REST APIs, never through direct local variable imports.

### 4. Identity Verification (CIN) Schema Sync
**Current Prompt Logic:** *"Ask the caller for the last four digits of their national ID (CIN)."*  
**Issue:** The `customers` (CRM) database currently does not have a field for `cin_number`.  
**Requirement:** Update the Postgres CRM schema to include the CIN field for all clients so the LLM has a "source of truth" to verify against during the call.

**when we create the databases later for our business logic (crm,sim,oss,ocs..)

---

### 5. Independent Technical Observations (Reviewer Notes)

*   **PII Exposure in Logs:** I noticed that some worker logs are printing customer metadata in cleartext. This violates the Blueprint §14 (PII-Shield). Ensure `CIN` digits and phone numbers are masked in all `structlog` outputs.
*   **Hardcoded Service Ports:** The `.env` and `settings.py` are strictly tied to `localhost` ports (8101, 8102, etc.). For a scalable platform, these should be mapped through a Docker internal DNS (e.g., `http://context-service:80`).
*   **Error Code Standardization:** When the `policy-service` returns a `REFUSED` status, the Agent Worker sometimes fails to handle the reason-code gracefully, leading to generic "I encountered an error" voice responses. Need a standard JSON error mapping between Services and the Worker.



also on the consent task i see :

class ConsentTask:
    """Run at TriageAgent.on_enter before any business talk (Phase 3)."""

    but weve alraedy implementt phase 3 so why this contsenttask still empty ?!