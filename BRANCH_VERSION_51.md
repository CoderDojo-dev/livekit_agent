# version_51 — HTTP Client Pool Cleanup + Clarification Streak Fix

## Summary
Two stability fixes: (1) release `httpx.AsyncClient` connection pools at end of every job to prevent socket leaks across many calls, and (2) fix the clarification counter to only count consecutive deferrals on the same ambiguous topic (prevent premature escalation after the caller moves on).

## HTTP Client Pool Cleanup (Patch #10)

**Problem:** Every typed HTTP client (context, decision, execution, NMS, notification, policy) opens a persistent `httpx.AsyncClient` pool on first use. LiveKit creates one process per job — after many calls, unused but still-open pools accumulate connections and file descriptors. No cleanup was registered.

**Solution:** `clients/__init__.py` rewritten to export `aclose_all_clients()`:
- Iterates over all 6 client getters (`get_context_client`, `get_decision_client`, `get_execution_client`, `get_nms_client`, `get_notification_client`, `get_policy_client`)
- Uses `functools.lru_cache.cache_info().currsize` to only close clients that were actually instantiated during this job (never opens a pool just to close it)
- Calls `await client.aclose()` on each active client via `asyncio.gather`
- Registered as `ctx.add_shutdown_callback(aclose_all_clients)` in `server.py`
- Catches and logs all exceptions — cleanup must never break shutdown

**MCP clients intentionally excluded:** their `MCPServerHTTP` lifecycle is owned by the LiveKit framework and closed with the session. Double-closing would crash.

## Clarification Streak Fix (Patch #5)

**Problem:** When the agent asked a clarification question (e.g. "Do you need billing or technical help?") and the caller answered, `clarification_attempts` kept incrementing. If the agent had asked 2+ clarifications *during the entire call*, it escalated to manager — even though the caller had clearly answered and moved on. This caused false escalations on long calls where the agent needed multiple clarifications on *different* topics.

**Solution:** A `_clarification_pending` flag on `SessionUserData`:
1. When `request_clarification` is called → sets `_clarification_pending = True`
2. In `BaseTelecomAgent.on_receive` (base_agent.py):
   - If `_clarification_pending` is True → caller is responding to the pending clarification → **preserve the streak** (`_clarification_pending = False`, keep `clarification_attempts`)
   - If `_clarification_pending` is False → caller changed topic or this is a new turn → **reset the counter** (`clarification_attempts = 0`)
3. Only `request_clarification` itself sets the flag (not other tools), so normal tool calls never trigger clarification tracking

## No Container / SDK Changes
No Dockerfile, docker-compose, or library version changes in this version.

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `apps/agent-worker/src/clients/__init__.py` | MODIFIED | New aclose_all_clients() — cleanup all httpx pools at job shutdown |
| `apps/agent-worker/src/server.py` | MODIFIED | Register ctx.add_shutdown_callback(aclose_all_clients) |
| `apps/agent-worker/src/session/session_state.py` | MODIFIED | Add _clarification_pending flag |
| `apps/agent-worker/src/tools/clarification_tools.py` | MODIFIED | Set _clarification_pending=True on clarification request |
| `apps/agent-worker/src/agents/base_agent.py` | MODIFIED | Reset clarification_attempts when caller moves on without pending clarification |
| `commands.md` | MODIFIED | Fixed missing code block markers |
