# Version 62 — ManagerAgent Uniform Instruction Assembly + Closing/Language Policy

> **Base branch:** `version_61`
> **Files changed:** 2 (+273 / -13) — 1 modified + 1 new
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

### ManagerAgent Instruction Gap Fix

**Problem:** The `ManagerAgent` was the only persona still passing a raw instruction string to `super().__init__()`. While the other four personas (triage, billing, account_services, technical) received their instructions through `merge_instructions()` — which assembles shared layers like `CLOSING_PROTOCOL`, `LANGUAGE_SWITCH_POLICY`, the TTS reminder, and the `NO_DEAD_END_MANDATE` routing guard — the ManagerAgent received none of these.

**Six defects identified and fixed:**

| # | Defect | Impact |
|---|--------|--------|
| 1 | `CLOSING_PROTOCOL` absent | Agent didn't know the proper call-ending flow: ask if anything else, confirm, then `end_conversation` |
| 2 | `LANGUAGE_SWITCH_POLICY` absent | No mechanism to handle a caller explicitly requesting a language switch mid-call |
| 3 | TTS language lock reminder absent | Weaker language anchoring than all other personas |
| 4 | `NO_REDIRECT` guard absent | Agent could tell callers to call another department — a dead end, since the Manager IS the final escalation point |
| 5 | `end_conversation` tool given but never explained | Tool available, instructions say nothing about when to use it |
| 6 | `switch_spoken_language` tool given but never explained | Tool available, instructions say nothing about it |

**Fix:** Instructions rebuilt from a list join:
1. Core instructions + added `NO_REDIRECT` sentence ("you are the final escalation point")
2. `CLOSING_PROTOCOL`
3. `LANGUAGE_SWITCH_POLICY`
4. TTS language reminder

Imports `CLOSING_PROTOCOL` and `LANGUAGE_SWITCH_POLICY` from `base_agent.py`. **Zero changes** to `base_agent.py` or any other file — this is a single-file fix.

### Validation Checks

`scripts/manager_v62_checks.py` — 28 checks in 5 sections:

| Section | Focus | Checks |
|---------|-------|--------|
| A | Opus proposition | Mandate byte-for-byte reproduction |
| B | Current state v61 | Tool citation audit across all 5 personas |
| C | ManagerAgent audit | 6 defects confirmed via assertions |
| D | Fix verification | 13 checks: no missing tools, shared layers present, language anchoring matches specialists |
| E | Non-regression | `base_agent.py` unchanged, `merge_instructions` unchanged, other 4 personas unaffected |
