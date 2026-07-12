# version_24 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. Knowledge RAG Persistence (New Schema)
- **New file**: `packages/persistence/src/persistence/models/knowledge.py` — 4 tables in `knowledge` schema
  - `KnowledgeDocument` — versioned source documents stored in MinIO with checksum, language, document_type, status lifecycle (pending→processing→ready|failed|archived)
  - `KnowledgeChunk` — normalized chunks with Qdrant point ID, token count, embedding dimensions, active flag for soft-deletion, cascading FK to document
  - `KnowledgeIngestionJob` — auditable execution record per ingestion attempt with source_object_key, document/chunk/embedded counts, error details, timing
  - `KnowledgeSyncOutbox` — durable Postgres-to-Qdrant sync events with aggregate_type/id, operation (upsert/delete), status lifecycle, retry tracking
- **New migration**: `0010_knowledge_rag.py` — creates `knowledge` schema + 4 tables with constraints, indices, foreign keys
- Registered in `persistence/models/__init__.py`

### 2. SIP Transfer — Idempotency & Multilingual Announcements
- `human_transfer_in_progress` flag prevents concurrent transfer calls
- `human_transfer_announced` flag ensures exactly one component owns the spoken message (no duplicate "connecting you" announcements from ManagerAgent + routing + escalation)
- Multilingual transfer messages in `_TRANSFER_MESSAGES` dict (FR/AR/EN) using `say_and_wait`
- `transfer_to_human` returns `transfer_already_in_progress` if already transferring
- `human_transfer_in_progress` reset in `finally` block

### 3. Manager Agent — Immediate Transfer Without Speech
- Simplified `on_enter`: calls `transfer_to_human` immediately without generating spoken text first
- Instructions tightened: "Call transfer_to_human immediately and do not speak before calling it"

### 4. Escalation & Routing — No Duplicate Handoff Messages
- `escalate_to_manager` removed `handoff_with_message` call (ManagerAgent handles its own entry)
- `route_to_billing` / `route_to_technical` return Agent directly — no `handoff_with_message`
- `route_to_account_services` — **new tool** for phone line, plan, recharge, and roaming requests
- Triage agent: added `route_to_account_services` tool + updated instructions
- Test assertions updated: routing no longer produces `session.say` calls

### 5. Policy Engine — Explicit Action Authorization
- `SUPPORTED_ACTIONS` allowlist; unknown action → `POLICY_UNKNOWN_ACTION` (escalate, never default allow)
- `DEFAULT_ALLOW` renamed to `KNOWN_ACTION_AUTHORIZED` for transparency
- **New tests**: `test_unknown_action_fails_closed`, `test_known_account_action_is_explicitly_authorized`

### 6. Execution Service — Policy Verdict Validation
- `execute()` now looks up `PolicyVerdict` row and validates:
  - Verdict exists, is `AUTHORIZED`, matches requested action type, belongs to the same session
- Raises `ValueError` for missing/mismatched verdicts (fail-closed)
- `executor.py`: `SUPPORTED_ACTIONS` frozenset + `_require_supported_action()` guard on `dispatch()` and `target_domain()`

### 7. Session State — Transfer Flags
- `SessionUserData`: added `human_transfer_announced: bool` and `human_transfer_in_progress: bool`

### 8. Client Widget — Responsive Session Layout
- CSS custom properties (`--session-x`, `--session-orb-scale`, `--session-copy-opacity`, `--session-copy-shift`) drive layout transitions
- `data-session-active="true"` toggle on `.voice-shell` switches:
  - **Desktop**: Aura/controls shift left, copy fades out, conversation rail appears right
  - **Tablet (≤900px)**: vertical sequence, no horizontal shift
  - **Mobile (≤640px)**: compact padding, smaller orb
- New animations: `conversation-rail-enter`, `conversation-mobile-enter`
- Laptop-height optimization (≤800px): reduced padding, smaller orb
- `prefers-reduced-motion`: all transitions disabled
- `.live-conversation__heading` hidden (chrome removed from rail)

## Files Affected (16 files, +1286/-79)

| File | Status | Change |
|------|--------|--------|
| `packages/persistence/src/persistence/models/knowledge.py` | **New** | 339 lines: 4 knowledge tables |
| `packages/persistence/alembic/versions/0010_knowledge_rag.py` | **New** | 463 lines: migration |
| `packages/persistence/src/persistence/models/__init__.py` | Modified | Register knowledge model |
| `apps/agent-worker/src/telephony/sip_transfer.py` | Modified | Transfer idempotency + multilingual |
| `apps/agent-worker/src/agents/manager_agent.py` | Modified | Immediate transfer, no speech |
| `apps/agent-worker/src/agents/triage_agent.py` | Modified | Added route_to_account_services |
| `apps/agent-worker/src/tools/escalation_tools.py` | Modified | Removed handoff_with_message |
| `apps/agent-worker/src/tools/routing_tools.py` | Modified | New account services route; no handoff msg |
| `apps/agent-worker/src/session/session_state.py` | Modified | Transfer flags |
| `apps/agent-worker/tests/interruption/test_voice_flow.py` | Modified | Updated handoff assertions |
| `services/policy-service/src/policy_service/engine.py` | Modified | Explicit action allowlist |
| `services/policy-service/tests/test_policy.py` | Modified | New unknown action + known action tests |
| `services/execution-service/src/execution_service/service.py` | Modified | Policy verdict validation |
| `services/execution-service/src/execution_service/executor.py` | Modified | Supported actions guard |
| `apps/client-widget/src/App.tsx` | Modified | session-active data attr, layout classes |
| `apps/client-widget/src/index.css` | Modified | Responsive session layout (~300 lines) |
