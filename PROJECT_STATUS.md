# Telecom AI Platform Status & Overview

## 1. Requirements & Dependencies Status
The core packages and toolsets across the different project phases (Phase 3 through 5) have been systematically managed via `pyproject.toml` configurations. These are being populated into a unified virtual environment to secure application consistency across:
- `apps/agent-worker`
- `mcp-servers/knowledge-mcp`
- `services/context-service`
- `services/knowledge-service`

---

## 2. Deep Codebase Analysis & Current Infrastructure Overview

Based on the recent integrations up to Phase 5, the architecture strongly adheres to a Hexagonal/DDD structure aimed at decoupling the Real-time audio transport layers from the determinist telecom business logic. 

Here is what is actively modeled and running inside the repository:

### `apps/agent-worker` (Real-Time Orchestrator)
- **Architecture:** Serves as the central WebRTC endpoint connected directly to the LiveKit Server.
- **Capabilities:** Manages WebRTC events and leverages `triage_agent.py` and `billing_agent.py` for classifying customer intent. Integrates Silero Voice Activity Detection (VAD) coupled with streaming STT and TTS for continuous audio flow.
- **Resiliency:** Handles fallback pathways (`_resilience.py`) securely allowing failover logic between OpenAI/Deepgram/Azure if an outage occurs, and persists dialogue continuity using `session_state.py`.

### `services/context-service` (Customer Context Engine)
- **Architecture:** The dedicated domain service strictly tasked with resolving customer profile associations.
- **Capabilities:** Utilizing `aggregator.py` and `customer_context.py` to compile live MSISDN (Phone number) data, internet roaming statuses, and telecom package allowances prior to prompt injection. `mock_directory.py` serves as the test layer representation of the global carrier directory.

### `services/knowledge-service` & `mcp-servers` (RAG & Tooling layer)
- **Architecture:** The Retrieval-Augmented Generation implementation, separated carefully into an internal retrieval service and an external Model Context Protocol layer.
- **Capabilities:** `corpus.py` and `retriever.py` embed and retrieve telecom technical constraints. `knowledge_glpi_toolset.py` exposes read/write endpoints to an external GLPI Helpdesk so the AI logic can query existing tickets to halt redundancy.

---

## 3. Next Possible Steps & Implementations (Roadmap)

To push the environment completely toward production functionality, the pipeline requires:

1. **Deploying Deterministic Policies (Phase 6):** Complete the `decision-service` and `policy-service`. This will force all LLM generation intents (like unlocking a SIM card or issuing a payment) through an internal deterministic ruleset verifying balances/permission before final execution occurs.
2. **Action Execution Endpoints:** Build the `execution-service` to securely commit those approved actions to mock systems or APIs.
3. **Frontend Client Connection:** Initialize the `apps/client-widget` React front-end utilizing `@livekit/components-react` so testers/customers have a local interface to trigger WebRTC calls directly over the browser.
4. **Final Linguistic Testing:** Perform Arabic Text-To-Speech parity checks between Azure Neural and ElevenLabs models as prescribed by Phase-0 limits.

---

## 4. Required Setup & Environment Variables

To operate the Agent Worker and successfully test live routing, your `.env` target must contain both self-hosted connection parameters and cloud API keys:

### A. Core System Databases (Docker/Infrastructure)
*Started seamlessly with the `make up` command.*
- **Postgres:** Telecom CRM data structures and Decision tracking.
- **Redis:** Volatile memory for Caching and `session_state` aggregation across agent transfers.
- **Qdrant & MinIO:** Qdrant DB for vectorized Knowledge Base indexing, and MinIO object storage for persisting live audio records/receipts.

### B. LiveKit Configurations
- `LIVEKIT_URL` (locally hosted to default: `ws://localhost:7880`)
- `LIVEKIT_API_KEY` (Your LiveKit host identifier)
- `LIVEKIT_API_SECRET`

### C. Cloud AI API Requirements
- `OPENAI_API_KEY` (Primary Agent Conversational Engine)
- `DEEPGRAM_API_KEY` (Primary endpoint for low-latency Speech-to-Text transcription)
- `ELEVENLABS_API_KEY` (Primary endpoint for Text-to-Speech synthesis)
- *(Optional)* `AZURE_SPEECH_KEY`, `GOOGLE_API_KEY` (Used by the AI Worker exclusively to sustain fallback topologies if primaries fail).

### D. External IT/Telecom Platforms
- Target Endpoints and credentials aligning to your GLPI instances for testing the MCP integrations.

---

## 5. Source Control
- **Remote Repository:** [https://github.com/chouaib-saad/livekit_agent](https://github.com/chouaib-saad/livekit_agent)
- **Branches:**
  - `main`: Core production-ready code.
  - `version_2.0`: Latest feature updates, security hygiene patches, and infrastructure optimizations (pushed July 1, 2026).
- **Initial Sync Date:** July 1, 2026
