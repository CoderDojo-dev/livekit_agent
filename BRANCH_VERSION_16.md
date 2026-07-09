# version_16 — Fix Missing `await` on Agent `on_enter`, Refactor TTS Chain, Move tracemalloc

## Purpose
Fix a silent call-killing bug where 5 of 5 agent `on_enter()` methods fired `session.generate_reply()` without `await`, causing the session to proceed before the greeting was spoken. Refactor the TTS provider chain to include Deepgram Aura as an emergency safety net and restore Azure as the final fallback, so Cartesia silence no longer means total silence. Move `tracemalloc` from module-level to per-job to avoid cross-job state contamination.

## Major Changes

### 1. Missing `await` Fix (5 agents, 1 root cause)
All five agent `on_enter()` methods called `self.session.generate_reply(...)` — a coroutine — without `await`. This meant the LLM call was fire-and-forget: the session moved on immediately, the greeting never completed before the next turn started.

| Agent | File | Fix |
|-------|------|-----|
| `TriageAgent` | `triage_agent.py:67` | Added `await` |
| `AccountServicesAgent` | `account_services_agent.py:32` | Added `await` |
| `BillingAgent` | `billing_agent.py:89` | Added `await` |
| `TechnicalAgent` | `technical_agent.py:79` | Added `await` |
| `ManagerAgent` | `manager_agent.py:33` | Added `await` |

### 2. TTS Provider Chain Refactor
The chain was silently down to a single provider (Cartesia only) because `ELEVEN_API_KEY` is empty and Azure was never wired. Now:

| Priority | Provider | Key | Status |
|----------|----------|-----|--------|
| 1 (Primary) | ElevenLabs | `ELEVEN_API_KEY` | Skipped if empty (unchanged) |
| 2 (Fallback) | Cartesia | `CARTESIA_API_KEY` | Unchanged |
| 3 (Safety net) | Deepgram Aura | `DEEPGRAM_API_KEY` | **NEW** — emergency fallback using existing key; try/except for `api_key=` kwarg compatibility |
| 4 (Final) | Azure | `AZURE_SPEECH_KEY` | **Restored** — was removed in earlier versions; now wired with `speech_key`, `speech_region`, `voice` |

**Other changes:**
- Raise `RuntimeError` if zero providers configured (fail fast instead of silent silence)
- Log configured provider types at startup for debugging

### 3. tracemalloc Placement
- **Before (v15)**: `tracemalloc.start(25)` at module import — allocs accumulated across jobs
- **After (v16)**: `tracemalloc.start(10)` inside `entrypoint()` — per-job, lower frame depth (10 instead of 25) for lower overhead

## Files / Modules Affected (8 files)

| File | Change |
|------|--------|
| `apps/agent-worker/src/agents/triage_agent.py` | +1/-1: `generate_reply` now awaited |
| `apps/agent-worker/src/agents/account_services_agent.py` | +1/-1: `generate_reply` now awaited |
| `apps/agent-worker/src/agents/billing_agent.py` | +1/-1: `generate_reply` now awaited |
| `apps/agent-worker/src/agents/technical_agent.py` | +1/-1: `generate_reply` now awaited |
| `apps/agent-worker/src/agents/manager_agent.py` | +1/-1: `generate_reply` now awaited |
| `apps/agent-worker/src/providers/tts.py` | +31/-24: Deepgram + Azure fallbacks, RuntimeError, provider logging |
| `apps/agent-worker/src/providers/stt.py` | +1/-1: trailing newline (cosmetic) |
| `apps/agent-worker/src/server.py` | +3/-4: tracemalloc moved to per-job, depth 25→10 |

## Differences from version_15

| Aspect | version_15 | version_16 |
|--------|-----------|-----------|
| Agent on_enter | 5/5 missing `await` (silent bug) | All 5 correctly awaited |
| TTS providers | Cartesia only (single point of failure) | 4 providers: ElevenLabs + Cartesia + Deepgram + Azure |
| Azure TTS | Not wired | Wired as final fallback |
| Deepgram TTS | Not used for TTS | Emergency safety net |
| tracemalloc | Module-level (cross-job), depth 25 | Per-job, depth 10 |