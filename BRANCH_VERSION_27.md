# version_27 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. Execution Service — HTTP Error Handling
- `main.py`: `execute()` wrapped in try/except — `ValueError` → 400 (e.g. unsupported action, mismatched verdict), generic `Exception` → 503 (service unavailable)
- Both return `HTTPException` with the original exception detail string

### 2. Execution Client — Richer Error Messages
- `execution_client.py`: HTTP error handling now extracts `detail` from JSON error response body when available (fallback to string representation)
- Failed outcome includes user-facing message: "This service is currently unavailable, please try again later. Apologize briefly and offer to escalate."

### 3. Outcomes — Optional Message Parameter
- `outcomes.py`: `failed()` now accepts optional `message` parameter overriding the default "The action could not be completed right now. Apologize briefly and offer to escalate."

### 4. Executor — Trailing Newline
- `executor.py`: minor trailing newline fix (no functional change)

### 5. Tests — Remove Default Fallback Assertions
- `test_executor.py`: `target_domain("SOMETHING_ELSE")` now expects `ValueError` (was `== "execution"`)
- `dispatch("MYSTERY", {})` now expects `ValueError` (was `.startswith("ACT-")`)

## Files Affected (5 files, +26/-9)

| File | Status | Change |
|------|--------|--------|
| `services/execution-service/src/execution_service/main.py` | Modified | ValueError→400, Exception→503 |
| `apps/agent-worker/src/clients/execution_client.py` | Modified | JSON error detail extraction + user message |
| `apps/agent-worker/src/tools/outcomes.py` | Modified | failed() optional message param |
| `services/execution-service/src/execution_service/executor.py` | Modified | Trailing newline |
| `services/execution-service/tests/test_executor.py` | Modified | ValueError assertions for unknown actions |
