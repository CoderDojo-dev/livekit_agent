# Version 63 — Naturalness v63: Human-like Prompts, Localized Fallback, Honest Transfer

> **Base branch:** `version_62`
> **Files changed:** 7 (+309 / -37) — 6 modified + 1 new
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

### Naturalised Identity Prompts (`identity_verification_task.py`)

All 5 prompt dictionaries (`_PROMPTS`, `_RETRY`, `_INVALID`, `_SUCCESS`, `_FAILURE`) were rewritten from short, robotic text to warm, conversational speech that sounds like a real call-center advisor.

**Before (French example):**
```
"Pour vérifier votre identité, dites uniquement les quatre derniers chiffres de votre CIN."
"Merci, votre identité est confirmée."
"Je n'ai pas pu vérifier votre identité. L'action sensible ne sera pas exécutée."
```

**After:**
```
"Avant d'aller plus loin, j'ai juste besoin de m'assurer que c'est bien vous : pouvez-vous me donner les quatre derniers chiffres de votre CIN ?"
"Parfait, merci, c'est bien vous. Je continue."
"Je suis désolé, je n'arrive pas à confirmer votre identité pour le moment, je ne vais donc pas pouvoir procéder à cette opération. Mais je reste avec vous pour trouver une solution."
```

All three languages (fr, ar, en) were updated. System vocabulary removed ("action sensible", "sensitive action", "الإجراء الحساس"). Structure constants unchanged (`MAX_ATTEMPTS=3`, `TASK_DEADLINE_S=30.0`, `VERIFY_CALL_TIMEOUT_S=5.0`).

### Localised Payment Fallback (`payment_confirm_task.py`)

The `_fail_closed` method previously hardcoded a French literal:
```python
await self.session.say("Je n'ai pas reçu de confirmation claire, je n'effectue pas le paiement.")
```

Now uses `_NO_CONFIRMATION` dict (`{fr, ar, en}`) with a `_language()` method matching the pattern from `IdentityVerificationTask`. A caller speaking Arabic or English correctly hears their own language even on payment timeout/failure.

### Naturalised Outcome Messages (`outcomes.py`)

All three outcome factory functions (`refused()`, `escalate()`, `failed()`) received updated `message` fields:

| Function | Old instruction | New instruction |
|----------|---------------|-----------------|
| `refused` | "Offer an alternative if one exists." | "Tell the caller warmly, in plain spoken words, the way a human advisor would — never read rule identifiers, internal codes, or technical wording aloud." |
| `escalate` | "Explain briefly, then call escalate_to_manager." | "Say it briefly and warmly in plain spoken words — no codes. If the caller was ALREADY told this out loud, do NOT repeat it: simply acknowledge and move on." |
| `failed` | "Apologize briefly and offer to escalate." | "Apologize sincerely and naturally, the way a human advisor would, without technical wording, and offer to escalate." |

### Honest Manager Transfer (`manager_agent.py`)

**Problem:** The ManagerAgent waited for an LLM generation turn before calling `transfer_to_human`. The escalating persona had already announced the transfer, so a generated turn could only duplicate or contradict the announcement — wasting TTS and confusing the caller.

**Fix:**
- `on_enter` now runs `transfer_to_human` **immediately** using a minimal `_TransferContext` shim (two-attribute RunContext stand-in)
- Successful transfer raises `StopResponse` — the caller's leg is gone, so no speech is generated into an empty room
- Callback / declined / failure produces one short wrap-up turn driven by the tool's own `message` field — never invented
- Instructions updated: transfer FIRST, ticketing/closing only after the tool answers

### Skill-tagged Escalation (`escalation_tools.py`)

**Problem:** `current_persona_skill_tag` defaulted to `"general"` for all escalations because it was never assigned. The routing system couldn't distinguish a billing escalation from a technical one, causing generalist advisors to handle domain-specific escalations.

**Fix:** Added `_skill_tag_for(context)` which derives the tag from the persona type:
- `BillingAgent` → `"billing"`
- `TechnicalAgent` → `"technical"`
- `AccountServicesAgent` → `"account"`
- `TriageAgent`/unknown → `"general"`

Sets `user_data.current_persona_skill_tag` and `user_data.human_transfer_announced = True` before creating the ManagerAgent.

### SIP Transfer Improvements (`sip_transfer.py`)

- `transfer_to_human` raises `StopResponse` on successful SIP transfer (stops the turn, no TTS billed for empty room)
- Added `_language()` helper tolerating enum/locale values (matching the pattern used elsewhere)
- Added `message` field to `callback_declined` and `transfer_already_in_progress` outcomes
- **Specialist fallback fix**: when no specialist advisor is free for a skill tag (e.g. no "billing" advisor), falls back to a generalist advisor before offering a callback — prevents premature callbacks

### Validation Checks

`scripts/naturalness_v63_checks.py` — Static checks across sections A-E covering identity dict keys and system vocabulary, payment localization, outcomes naturalization, and file scope.
