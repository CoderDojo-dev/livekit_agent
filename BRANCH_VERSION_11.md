# version_11 — LLM Provider Chain Refactor & Full Event Handler Migration

## Purpose
Rework the LLM provider chain so the agent can use OpenAI as primary when available (controlled by `OPENAI_ENABLED`), and complete the migration of all remaining deprecated LiveKit session event handlers to their verified 1.6.3 equivalents.

## Major Changes

### 1. LLM Provider Chain Refactor
- **New `openai_enabled` parameter**: Passed from settings → `session_factory` → `build_llm()`
- **When `OPENAI_ENABLED=true`**:
  - **Primary**: OpenAI GPT-4o-mini via `livekit.plugins.openai.LLM`
  - **First fallback**: Google Gemini 2.5 Flash via `livekit.plugins.google.LLM`
  - **Subsequent fallbacks**: NVIDIA NIM → Groq (unchanged)
- **When `OPENAI_ENABLED=false`** (default, matches current `.env`):
  - **Primary**: Google Gemini 2.5 Flash (unchanged)
  - **OpenAI skipped entirely** — no dead weight in the fallback chain
  - **Fallbacks**: NVIDIA NIM → Groq (unchanged)

### 2. Full Event Handler Migration (all 4 events)
All deprecated LiveKit session events are now migrated to their verified 1.6.3 names:

| Old (deprecated) | New (1.6.3) | Status |
|---|---|---|
| `user_speech_committed` | `conversation_item_added` (role="user" check) | **NEW in v11** |
| `agent_speech_committed` | `conversation_item_added` (role="assistant" check) | Migrated in v10 |
| `function_calls_collected` | `function_tools_executed` | **NEW in v11** |
| `function_calls_finished` | `function_tools_executed` (merged single event) | **NEW in v11** |

### 3. pydantic Version Widen
- **Constraint**: `==2.10.4` → `>=2.11,<3`
- **Why**: Required by `mcp>=1.24` dependency and future compatibility with livekit-agents plugin versions

## Files / Modules Affected (5 files)

| File | Change |
|------|--------|
| `apps/agent-worker/pyproject.toml` | `pydantic==2.10.4` → `pydantic>=2.11,<3` |
| `apps/agent-worker/src/config/settings.py` | Comment update for new LLM chain logic |
| `apps/agent-worker/src/providers/llm.py` | Full refactor: `openai_enabled` flag, dynamic provider ordering, OpenAI skipped when disabled |
| `apps/agent-worker/src/providers/session_factory.py` | Pass `settings.openai_enabled` to `build_llm()` |
| `apps/agent-worker/src/server.py` | Migrate 3 remaining deprecated events; add type annotations (ConversationItemAddedEvent, FunctionToolsExecutedEvent, ChatMessage) |

## Differences from version_10

| Aspect | version_10 | version_11 |
|--------|-----------|-----------|
| LLM chain | Fixed Gemini primary + OpenAI fallback | Configurable primary (OpenAI when enabled, Gemini otherwise) |
| OPENAI_ENABLED | Not respected | Controls provider ordering + skip |
| pydantic | `==2.10.4` | `>=2.11,<3` |
| Event: user speech | `user_speech_committed` (dead) | `conversation_item_added` (role check) |
| Event: function calls | `function_calls_collected` + `function_calls_finished` (both dead) | `function_tools_executed` (single, verified) |
| Event: agent speech | `conversation_item_added` (v10 fix) | `conversation_item_added` (unchanged) |
| Event handler types | Un-typed | Typed (ConversationItemAddedEvent, etc.) |
