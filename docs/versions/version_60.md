# Version 60 — Recording Consent Toggle, TTS Audit Pipeline, Deepgram Keyterms Fix

> **Base branch:** `version_59`
> **Files changed:** 8 (+600 / -6) — 5 modified + 3 new
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

### Recording Consent Toggle

**`RECORDING_CONSENT_ENABLED`** (env var, default `true`).

When set to `false`, the triage agent skips the entire `ConsentTask` (the "this call may be recorded" prompt) and immediately sets `user_data.recording_consent = False`. This saves approximately **24% of TTS per call** — one full LLM+TTS round-trip that is only informational and doesn't affect functionality.

All consent logic in `ConsentTask` remains intact and testable. Only the gate in `triage_agent.py` checks the flag. Setting to `false` is intended for development only — production must always collect consent.

### TTS Audit Pipeline

A new non-invasive instrumentation layer that answers the question: **"How many characters am I sending to Cartesia, and how many are actually played to the caller?"**

When `TTS_AUDIT=1` is set, the instrumentation monkey-patches four LiveKit classes:
- **`FallbackAdapter.__init__`** — logs when a TTS chain is created, including which providers and who built it
- **`TTS.aclose`** — logs when a chain is closed (to detect leaks)
- **`SynthesizeStream`** — logs every `push_text`/`flush`/`end_input`/`aclose` call, accumulating per-stream character counts
- **`ChunkedStream.__init__`** — logs non-streaming synthesis with full text
- **`ConnectionPool._prewarm_impl` / `_connect`** — logs pool events

Output is JSONL to `/tmp/tts_audit.jsonl` (configurable via `TTS_AUDIT_LOG`), flushed after every write for live `tail -f` analysis.

**Three waste sources targeted:**

| Code | Symptom | Expected fix |
|------|---------|-------------|
| n1 | Characters sent to provider but never played | Measure preemptive generation waste |
| n2 | Multiple TTS chains per call instead of 1 | Track chain creation and closure |
| n3 | Same text synthesized N times across handoffs | Detect repeated digest |

**New files:**

| File | Purpose |
|------|---------|
| `providers/tts_audit.py` | Runtime instrumentation (patches LiveKit classes) |
| `scripts/tts_audit_report.py` | Reconciliation report: loads JSONL, prints chain count, duplicates, over-synthesis ratio |
| `scripts/tts_audit_static.py` | Static analysis: builds TTS chains without synthesizing (zero Cartesia cost) |

All instrumentation is zero-cost when `TTS_AUDIT != 1` — only a single boolean check at import time.

### Deepgram Keyterms Compatibility Fix

In `stt.py`, the keyterms parameter name changed between Deepgram plugin versions:
- Older: `"keyterm"` (singular)
- Newer: `"keyterms"` (plural)

The code now tries both names in a for loop with `inspect.signature` detection, logging which was accepted. Previously only `"keyterms"` was tried, which silently failed on older plugin versions.
