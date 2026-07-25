# Version 51 — HTTP Client Pool Cleanup & Clarification Streak Fix

## What's new
- **`aclose_all_clients()`**: closes every typed httpx.AsyncClient pool (context, decision, execution, NMS, notification, policy) — only those actually instantiated (via `lru_cache.currsize`). Registered as shutdown callback in `server.py`. MCP sessions excluded (LiveKit-owned)
- **Clarification streak fix**: new `_clarification_pending` flag on `SessionUserData`. When the agent calls `request_clarification`, flag is set. In `base_agent.on_receive`, if caller changed topic without a pending clarification, the counter resets — prevents premature escalation after caller moves on from an ambiguous topic
