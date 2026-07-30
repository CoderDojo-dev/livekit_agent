# Version 69 — Centralised Escalation Policy, Consent Refusal, Sentiment Tuning

> **Base branch:** `version_68`
> **Files changed:** 15 modified, 3 new (+233 / -60)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### 1. Centralised Escalation Policy (`tools/escalation_policy.py` — NEW)
- `EscalationPolicy` dataclass with configurable thresholds: `max_clarifications=3`, `max_identity_failures=3`, `max_negative_turns=3`.
- `decide(user_data, explicit_reason)` — single function that determines the strongest escalation trigger. Replaces scattered `_trigger_for` logic.

### 2. `caller_refused_manager` Tool (NEW)
- Registers the caller's explicit refusal (`user_refused_manager=True`), stops all future escalation offers, and returns a warm "no problem, I'll keep helping" response in the caller's language.
- Added to all 5 personas (triage, billing, account_services, technical) + `KNOWN_TOOL_VOCABULARY`.

### 3. Three-Offer Escalation Cap
- After 3 offers refused (`_MAX_OFFERS=3`, tracked via `user_data.offer_count`), a deterministic hard-failure message is spoken: polite advice to call back later or contact through another channel.
- `can_hardfail` guard allows turning this off when the caller has already refused once.

### 4. Clarification Threshold 2→3 (`clarification_tools.py`)
- Escalation offered after 3 clarification attempts (was 2).
- Third attempt offers transfer with caller consent instead of forcing it.
- Uses `decide()` from escalation_policy.

### 5. Sentiment Threshold 2→3 (`sentiment/sentiment_scorer.py`)
- `ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS`: 3 (was 2).
- New `detect_abuse()` function scans transcript for abusive/threatening words (en/fr/ar).
- Removed "cancel", "complaint", "résilier" from negatives — these are legitimate requests, not frustration.

### 6. BaseAgent Sentiment→Escalation Integration
- Uses `decide(user_data)` instead of checking `should_offer_escalation` directly.

### 7. SIP Transfer Cleanup (`telephony/sip_transfer.py`)
- `_offer_callback` no longer passes deprecated `tts=` param to `CallbackScheduleTask`.

### 8. New Tests
| Test | Purpose |
|------|---------|
| `tests/transfer/test_callback_wiring.py` | Verifies callback chain passes `reason=` and `customer_context=` |
| `services/notification-service/tests/test_twilio_url.py` | Ensures Twilio URL uses single-brace f-strings |

### Files Changed (15 modified, 3 new)

| Area | Summary |
|------|---------|
| `tools/escalation_policy.py` **NEW** | Centralised policy + `decide()` function |
| `tools/escalation_tools.py` | `caller_refused_manager` tool, three-offer cap, hard-failure, uses `decide()` |
| `tools/clarification_tools.py` | Threshold 2→3, offers escalation on 3rd, uses `decide()` |
| `sentiment/sentiment_scorer.py` | Threshold 2→3, `detect_abuse()`, cleaned negative word list |
| `agents/base_agent.py` | Uses `decide()` for sentiment→escalation |
| `agents/instruction_kit.py` | Added `caller_refused_manager` to vocabulary |
| `agents/*_agent.py` (4 files) | Added `caller_refused_manager` tool |
| `session/session_state.py` | Added `offer_count`, `user_refused_manager`, `can_hardfail` |
| `telephony/sip_transfer.py` | Removed deprecated `tts=` param |
| `tests/` (5 files) | Updated for new thresholds + new test files |
