# version_20 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches. Identity verification rewritten from ephemeral in-memory to persisted, customer-bound, and time-limited. Every verification attempt is stored in PostgreSQL, bound to the specific customer, and expires after a configurable TTL.

## Changes & Patches

### 1. New Auth Model + Migration
- **New file**: `packages/persistence/src/persistence/models/auth.py`
- **New file**: `packages/persistence/alembic/versions/0009_auth_identity.py`
- **Table**: `verification_sessions` — stores customer_id, CIN hash (last 4 digits), attempt_count, verified (bool), expires_at per verification session
- **Registered** in `persistence/models/__init__.py`

### 2. Context-Service Auth Logic
- **New file**: `services/context-service/src/context_service/auth_service.py`
  - `verify_cin_last4()`: persists each attempt to DB, enforces max attempts per session, returns structured result with `verification_session_id`, `verified_customer_id`, `verification_level`, `verified_at`, `expires_at`, `attempt_count`

### 3. Identity Verification Client (agent-worker → context-service)
- `context_client.py`: `verify_identity()` now sends `call_session_id` alongside `customer_id`/`answer` and returns a rich dict instead of a bare bool
- Graceful failure: returns `{"verified": False, "status": "failed", "reason": "context_service_unavailable"}` on HTTP error

### 4. Guards — Freshness + Customer Binding
- `guards.py`: New `identity_is_fresh()` — requires `identity_verified=True`, `verified_customer_id == customer.customer_id`, and `expires_at > now()`
- `ensure_identity_verified()`: verify callback now stores all verification metadata (session_id, level, method, verified_customer_id, verified_at, expires_at) onto `SessionUserData`
- `SessionUserData` gains 6 new fields: `verified_customer_id`, `verification_level`, `verified_at`, `expires_at`, `verification_method`, `verification_session_id`

### 5. Policy Engine — Identity Freshness Checks
- `engine.py`: New verdicts for SENSITIVE_ACTIONS:
  - `IDENTITY_CUSTOMER_MISMATCH` — verification must be bound to the action customer
  - `IDENTITY_EXPIRED` — verification must not have expired
- `PolicyContext` gains `verified_customer_id` and `identity_expires_at` fields
- `guarded_action.py`: Passes `verified_customer_id` and `identity_expires_at.isoformat()` to policy context

### 6. Server Routing — Trusted MSISDN from Participant Attributes
- `server.py`: MSISDN now sourced from `participant.attributes["telecom.caller_msisdn"]` instead of `settings.session_caller_msisdn`
- `wait_for_participant()` added to entrypoint before prefetch
- Language auto-detected from customer snapshot
- `_open_conversation()` uses `customer.msisdn` instead of config value

### 7. Token-Service — Pilot MSISDN Attribute
- `token-service/main.py`: Injects `PILOT_MSISDN` as `telecom.caller_msisdn` participant attribute in the JWT token
- TTL reduced from 1 hour to 15 minutes
- Grants restricted to `room_join=True` only (no `room_create`, no `can_update_own_metadata`)

### 8. Tests — Policy Freshness Coverage
- `test_policy.py`: 3 new test cases:
  - `test_verified_identity_must_match_action_customer` → `IDENTITY_CUSTOMER_MISMATCH`
  - `test_expired_identity_cannot_authorize_action` → `IDENTITY_EXPIRED`
  - `test_missing_customer_binding_fails_closed` → `IDENTITY_CUSTOMER_MISMATCH`
- All existing tests updated with `verified_customer_id` + `identity_expires_at` in test fixtures

### 9. Seed Data
- **New file**: `packages/persistence/seed/seed_auth_credentials.py` — seeds initial CIN credentials for pilot customers

## Files / Modules Affected (16 files, +981/-45)

| File | Status | Change |
|------|--------|--------|
| `packages/persistence/src/persistence/models/auth.py` | **New** | 4678 bytes: verification_sessions table model |
| `packages/persistence/src/persistence/models/__init__.py` | Modified | +1: register auth model |
| `packages/persistence/alembic/versions/0009_auth_identity.py` | **New** | 7501 bytes: migration creating verification_sessions |
| `packages/persistence/seed/seed_auth_credentials.py` | **New** | 2105 bytes: pilot CIN seed data |
| `services/context-service/src/context_service/auth_service.py` | **New** | 5463 bytes: verify_cin_last4() persistence logic |
| `services/context-service/src/context_service/main.py` | Modified | Wire auth_service; structured response |
| `services/context-service/src/context_service/schemas.py` | Modified | VerifyIdentityRequest gains call_session_id; response gains 7 fields |
| `apps/agent-worker/src/clients/context_client.py` | Modified | verify_identity returns rich dict; call_session_id param |
| `apps/agent-worker/src/tools/guards.py` | Modified | identity_is_fresh() + persisted verify callback |
| `apps/agent-worker/src/session/session_state.py` | Modified | 6 new verification fields |
| `apps/agent-worker/src/tools/guarded_action.py` | Modified | Pass verification metadata to policy |
| `apps/agent-worker/src/server.py` | Modified | Trusted MSISDN from participant attributes; language auto-detect |
| `apps/token-service/src/token_service/main.py` | Modified | PILOT_MSISDN attribute; 15min TTL; restricted grants |
| `services/policy-service/src/policy_service/engine.py` | Modified | IDENTITY_CUSTOMER_MISMATCH + IDENTITY_EXPIRED checks |
| `services/policy-service/src/policy_service/schemas.py` | Modified | PolicyContext gains verified_customer_id + identity_expires_at |
| `services/policy-service/tests/test_policy.py` | Modified | 3 new test cases; all fixtures updated |
