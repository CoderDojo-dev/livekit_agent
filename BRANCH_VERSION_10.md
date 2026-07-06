# version_10 — MCP Version Fix & Event Handler Migration

## Purpose
Resolve the `TypeError` on `streamablehttp_client(http_client=...)` caused by an overly restrictive MCP SDK constraint, and restore agent speech logging that broke after the LiveKit 1.6.3 event API migration.

## Major Changes

### 1. MCP Dependency Fix
- **Constraint**: `mcp>=1.9,<1.10` → `mcp>=1.24,<2`
- **Why**: LiveKit agents 1.6.3 instantiates MCP clients with `streamablehttp_client(http_client=...)`. This keyword argument was not present in MCP `<1.24`, so the overly narrow pin `>=1.9,<1.10` caused a `TypeError` at runtime, blocking both the knowledge and ticketing MCP tool sets. Version 1.24+ is confirmed compatible with the call signature that livekit-agents 1.6.3 uses.

### 2. Agent Speech Logging Fix
- **Old event**: `agent_speech_committed` (removed/deprecated in livekit-agents 1.6.3)
- **New event**: `conversation_item_added` with role check for `"assistant"`
- **Why**: The deprecated event never fired, so agent speech was never logged — the `🤖 Agent:` lines were completely absent from logs. The `conversation_item_added` event is the verified replacement in the 1.6.3 event API.

## Files / Modules Affected (2 files)

| File | Change |
|------|--------|
| `apps/agent-worker/pyproject.toml` | `mcp>=1.9,<1.10` → `mcp>=1.24,<2` |
| `apps/agent-worker/src/server.py` | `agent_speech_committed` → `conversation_item_added` with role check |

## What Is NOT Changed (intentionally)
- **pydantic**: Remains at `==2.10.4` (no breaking upgrade)
- **livekit-agents dependency**: Remains extras-based (`livekit-agents[deepgram,elevenlabs,...]==1.6.3`)
- **OTel configuration**: Remains per-job (no module-level change)
- **Turn detection**: Unchanged
- **TTS/STT provider chain**: Unchanged
- **Event handlers for user speech and function calls**: Unchanged (still using `user_speech_committed` and `function_calls_collected`)

## Differences from version_09

| Aspect | version_09 | version_10 |
|--------|-----------|-----------|
| MCP version | `>=1.9,<1.10` (crashes) | `>=1.24,<2` (works) |
| Agent speech event | `agent_speech_committed` (dead) | `conversation_item_added` (verified 1.6.3) |
| pydantic | `==2.10.4` | `==2.10.4` (unchanged) |
| Event handlers | 4 deprecated names | 1 migrated (`agent_speech` → `conversation_item_added`), 3 still deprecated |
