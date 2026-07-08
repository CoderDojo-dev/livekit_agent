# version_14 — Implement Technical Tool Stubs, Add Identity Gates, Remove Dead Code

## Purpose
Replace three `NotImplementedError` stubs in `technical_tools.py` with working implementations so the TechnicalAgent can actually diagnose data issues, check network status, and unblock SIM pins. Add identity verification gates to all three account-sensitive tools (`change_plan`, `top_up`, `toggle_roaming`). Remove a dead observability stub that only raised `NotImplementedError`.

## Major Changes

### 1. Technical Tools — Stubs → Real Implementations
| Tool | Before | After |
|------|--------|-------|
| `diagnose_data_issue` | `raise NotImplementedError("wired in Phase 5")` | Reads customer context + calls `get_context_client().get_balance()`; returns structured diagnosis dict |
| `unblock_sim_pin` | `raise NotImplementedError("wired in Phase 7")` | Identity-gated, then `execute_guarded_action("UNBLOCK_SIM", {})` |
| `check_network_status` | `raise NotImplementedError("wired in Phase 8")` | Validates area input, returns local-safe "no known incident" response + guidance to create ticket |

### 2. Identity Gates on Account Tools
All three account-sensitive tools now call `ensure_identity_verified()` before reaching the guarded action path:

| Tool | Gate Added | Escalation on Failure |
|------|-----------|----------------------|
| `change_plan` | `ensure_identity_verified(context)` | `IDENTITY_REQUIRED` |
| `top_up` | `ensure_identity_verified(context)` | `IDENTITY_REQUIRED` |
| `toggle_roaming` | `ensure_identity_verified(context)` | `IDENTITY_REQUIRED` |

### 3. TechnicalAgent Tools Wired
- `diagnose_data_issue` and `check_network_status` imported and added to tool list
- Agent instructions updated to describe both tools

### 4. Dead Code Removal
- `metrics_hooks.py`: removed — was a stub class that only raised `NotImplementedError`

## Files / Modules Affected (4 files)

| File | Change |
|------|--------|
| `apps/agent-worker/src/tools/technical_tools.py` | +68/-3: 3 real implementations replace stubs |
| `apps/agent-worker/src/tools/account_tools.py` | +9/-4: identity gates on 3 tools |
| `apps/agent-worker/src/agents/technical_agent.py` | +7/-5: wire new tools + update instructions |
| `apps/agent-worker/src/observability/metrics_hooks.py` | Deleted (dead stub) |

## Differences from version_13

| Aspect | version_13 | version_14 |
|--------|-----------|-----------|
| Technical tools | `NotImplementedError` stubs | Working: diagnose, unblock_sim_pin, check_network |
| Account tool identity gates | None (direct guarded action) | All 3 gated: change_plan, top_up, toggle_roaming |
| TechnicalAgent tools | unblock_sim + replace_sim + MCP | + diagnose_data_issue + check_network_status |
| `metrics_hooks.py` | Dead stub present | Removed |
