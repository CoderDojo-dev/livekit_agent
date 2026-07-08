# version_13 — Bounded Task Deadlines, SIM Replacement Flow, Inter-Service Auth

## Purpose
Eliminate the single most impactful call-killing bug: AgentTask subclasses that hang indefinitely when the LLM never calls their completion tool. Every task now has a hard deadline watchdog that fail-closes to the safe default (no payment, no callback, no recording, no replacement). Add the SIM replacement flow (CDC 5.5) and inter-service auth headers to all MCP→service HTTP calls.

## Major Changes

### 1. Bounded Fail-Closed Task Pattern (all 5 AgentTask subclasses)
Every task now follows the same pattern: `_arm()` starts a watchdog, `_finish()` is idempotent and cancels the watchdog, `_fail_closed()` catches timeout/error.

| Task | Deadline | Fail-Closed Default |
|------|----------|---------------------|
| `ConsentTask` | 20s | `False` (no recording) |
| `IdentityVerificationTask` | 30s + 5s verify_fn timeout | `False` (escalate to human) |
| `PaymentConfirmTask` | 25s | `False` (no payment) |
| `CallbackScheduleTask` | 25s | `False` (no callback scheduled) |
| `SimReplacementTaskGroup` | 45s | `None` (no replacement request) |

### 2. Identity Verification Improvements
- `asyncio.wait_for(40s)` in `guards.py` — wraps the entire IdentityVerificationTask
- `VERIFY_CALL_TIMEOUT_S = 5.0` — bounds the context-service HTTP call
- LLM re-prompt on failed attempt instead of returning `False` immediately
- Counter incremented in try/except so a user-data serialization issue doesn't crash the session

### 3. SIM Replacement Flow (CDC 5.5)
- **New `SimReplacementTaskGroup`**: `AgentTask[dict|None]` collecting reason, delivery address, contact phone, optional delivery window
- **Validation + re-prompt**: Missing required fields trigger a re-prompt instead of silently completing with garbage
- **`replace_sim` tool** in `TechnicalAgent`: calls `SimReplacementTaskGroup`, identity-gated, then `execute_guarded_action("REPLACE_SIM", details)`

### 4. Inter-Service Auth Headers (INTERNAL_API_KEY)
All MCP servers now pass `X-API-Key` header on HTTP calls to domain services:

| MCP Server | Service Call | Header Added |
|------------|-------------|--------------|
| `ai-knowledge-rag` → `knowledge-service` | `POST /search` | `X-API-Key` |
| `messaging-gateway` → `notification-service` | `POST /notify` | `X-API-Key` |
| `ticketing-glpi` → `notification-service` | `POST /notify` | `X-API-Key` |

### 5. AttributeError Guard
- `guarded_action.py`: `getattr(customer, "account_age_days", 0)` prevents crash when customer context has no `account_age_days` field

## Files / Modules Affected (11 files, +458/-106)

| File | Change |
|------|--------|
| `apps/agent-worker/src/tasks/consent_task.py` | Complete rewrite: 20s deadline, watchdog, `_finish()`, `record_consent` tool |
| `apps/agent-worker/src/tasks/identity_verification_task.py` | Refactor: 30s deadline, 5s verify_fn timeout, re-prompt on failure |
| `apps/agent-worker/src/tasks/payment_confirm_task.py` | Full implementation: 25s deadline, `confirm_payment` tool |
| `apps/agent-worker/src/tasks/callback_schedule_task.py` | Refactor: 25s deadline, notification/writer wrapped in try/except |
| `apps/agent-worker/src/tasks/sim_replacement_task_group.py` | **New**: full `AgentTask[dict\|None]` with validation, re-prompt, cancel |
| `apps/agent-worker/src/tools/guards.py` | `asyncio.wait_for(40s)` wrapper, try/except on attempt counter |
| `apps/agent-worker/src/tools/guarded_action.py` | `getattr` guard for `account_age_days` |
| `apps/agent-worker/src/agents/technical_agent.py` | Wire `replace_sim` tool + `SimReplacementTaskGroup` import |
| `mcp-servers/ai-knowledge-rag/.../knowledge_search.py` | `X-API-Key` header on `/search` |
| `mcp-servers/messaging-gateway/.../messaging_ops.py` | `X-API-Key` header on `/notify` |
| `mcp-servers/ticketing-glpi/.../glpi_ticket_ops.py` | `X-API-Key` header on notification POST |

## Differences from version_12

| Aspect | version_12 | version_13 |
|--------|-----------|-----------|
| Task boundedness | No deadlines (tasks hung indefinitely) | Hard deadlines on all 5 AgentTasks |
| SIM replacement | Not implemented (stub returned `None`) | Full flow: collection + validation + guarded action |
| Identity verification | Stub (no timeout, no re-prompt) | 30s deadline, 5s verify timeout, LLM re-prompt on fail |
| Inter-service auth | No auth headers on MCP→service calls | `X-API-Key` on all 3 MCP HTTP calls |
| `account_age_days` guard | Direct attr access (crash risk) | `getattr` with default 0 |
