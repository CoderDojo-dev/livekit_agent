# Version 64 — Identity Verification: Numeric Speech Wins Over Spelled-out Digits

> **Base branch:** `version_63`
> **Files changed:** 1 (+8 / -0)
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

### Numeric Speech Priority in Digit Extraction

**Problem:** The `normalize_spoken_digits` function in `identity_verification_task.py` processes all tokens from the caller's speech through both the numeric and the `_WORD_DIGITS` (spelled-out number) paths. When a caller echoes the verification question and includes the spelled-out number — e.g.:

> "les QUATRE derniers, c'est 1234"

The word `"QUATRE"` is mapped via `_WORD_DIGITS` to `"4"`, adding a **fifth digit** on top of the four correct numeric digits `"1234"`. The resulting array has 5 elements instead of 4, so the function asks the caller to repeat — even though their answer was correct.

**Fix:** Added a short-circuit before the `_WORD_DIGITS` loop: if the input contains exactly 4 numeric digits (identified via `token.isdigit()`), return them immediately without processing spelled-out words at all. The `_WORD_DIGITS` fallback is only used when the input does NOT already contain exactly 4 numeric digits.

This is a minimal, single-file change with no external dependencies. All existing behavior for purely spoken-digit input (e.g., `"un deux trois quatre"` → `"1234"`) is preserved.
