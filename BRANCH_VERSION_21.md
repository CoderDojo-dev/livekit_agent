# version_21 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches

### 1. Triage Agent — No PII Before Verification
- Removed LLM-generated greeting by customer name (no longer discloses full name before identity verification)
- Uses pre-recorded `_GREETINGS` dict (FR/AR/EN) via `session.say()`
- Simplified agent instructions; language param resolved through lookup

### 2. Consent Task — Deterministic Multilingual Prompts
- Hard-coded FR/AR/EN prompt text in `_PROMPTS` dict; no LLM-generated consent question
- Watchdog timer starts only after playback completes (not on `on_enter`)
- Multilingual timeout message in `_TIMEOUTS`

### 3. Identity Verification — Spoken Digit Normalization
- `normalize_spoken_digits()`: extracts exactly 4 digits from numeric (4087), French (`quatre zéro huit sept`), Arabic (`أربعة صفر ثمانية سبعة`), or English (`four zero eight seven`) input
- All user-facing messages in `_PROMPTS`, `_RETRY`, `_INVALID`, `_SUCCESS`, `_FAILURE` — pre-recorded per language, no LLM-generated speech
- Invalid input (not exactly 4 digits) does NOT consume a persisted authentication attempt — only caller re-prompts
- **New file**: `apps/agent-worker/tests/identity/test_spoken_digits.py` — 5 test cases covering numeric, FR, AR, EN, and rejection of 3-digit input

### 4. Account Tools — Identity-Gated
- `get_plan_details()` now requires `ensure_identity_verified()` before returning data
- Returns structured dict with `masked_msisdn` and TTS-friendly `message` instead of raw string
- Returns `IDENTITY_REQUIRED` or `UNKNOWN_CALLER` escalation when gating fails

### 5. Billing Tools — Identity-Gated + Prepaid/Postpaid Branching
- `get_invoice_summary()`: identity-gated; returns `amount_due`, `currency`, `due_date`, `status` with TTS message
- `get_balance_summary()`: identity-gated; branches on `subscription_type`:
  - **Prepaid**: returns `credit`, `currency`, `data_remaining_mb`
  - **Postpaid**: returns latest invoice `amount_due`, `currency`, `status`, `due_date`
- Both return `IDENTITY_REQUIRED` or `UNKNOWN_CALLER` escalation when gating fails

### 6. Context-Service — Cleanup
- MSISDN normalization (strip whitespace) in `resolve_identity` and `get_context`
- `VerifyIdentityResponse.verified_at` / `expires_at` changed from `str` to `datetime`
- Docstring and formatting cleanup

### 7. Policy Tests — Formatting Cleanup
- `test_policy.py`: indentation fixed; no functional changes

## Files Affected (9 files, +449/-199)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/agents/triage_agent.py` | Modified | Deterministic greeting; no PII; simplified instructions |
| `apps/agent-worker/src/tasks/consent_task.py` | Modified | Multilingual prompts; timer-after-playback |
| `apps/agent-worker/src/tasks/identity_verification_task.py` | Modified | Spoken digit normalization; multilingual deterministic flow |
| `apps/agent-worker/src/tools/account_tools.py` | Modified | Identity-gated; structured response with masked MSISDN |
| `apps/agent-worker/src/tools/billing_tools.py` | Modified | Identity-gated; prepaid/postpaid branching |
| `apps/agent-worker/tests/identity/test_spoken_digits.py` | **New** | 5 test cases for digit normalization |
| `services/context-service/src/context_service/main.py` | Modified | MSISDN normalization; formatting |
| `services/context-service/src/context_service/schemas.py` | Modified | datetime types; docstring cleanup |
| `services/policy-service/tests/test_policy.py` | Modified | Indentation fix |
