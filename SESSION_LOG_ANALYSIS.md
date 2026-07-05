# Session Log Analysis — Telegram AI Voice Agent Platform
## Session: `telecom-support-1783191015454` — 2026-07-04 18:50 UTC

---

## 1. Issues Summary

| # | Issue | Severity | Phase | Current Status |
|---|-------|----------|-------|----------------|
| 1 | MCP `TypeError: streamablehttp_client()` — wrong `mcp` version in agent-worker container | **CRITICAL** | Startup | ❌ STILL BROKEN |
| 2 | Gemini LLM 400 — deadline too short (5s < 10s min) | **CRITICAL** | Inference | ❌ ALL GEMINI CALLS FAIL (4+ times) |
| 3 | NVIDIA NIM now works (was timing out before) | **RESOLVED** | Inference | ✓ FALLBACK TAKEOVER |
| 4 | STT Deepgram works correctly | **OK** | Transcription | ✓ |
| 5 | OpenTelemetry collector not running (`StatusCode.UNAVAILABLE`) | **WARNING** | Observability | ❌ OTEL traces lost |
| 6 | TTS Cartesia / ElevenLabs handoff — needs verification | **UNKNOWN** | Output | ? Not logged in this session |
| 7 | iPad STA / TOS disconnect triggered (stt eos while vad active) | **MINOR** | Transcription | ⚠ VAD/STT sync drift |
| 8 | Inference slower than realtime (multiple occurrences) | **MINOR** | Processing | ⚠ Latency spikes |
| 9 | Deprecated API warnings (turn_detection, preemptive_generation, metrics_collected) | **INFO** | Startup | ⚠ Will break in v2.0 |
| 10 | OTEL exporter configured twice (double config log) | **MINOR** | Startup | ⚠ Duplicate init |

---

## 2. Detailed Issue Analysis

### Issue 1: MCP `TypeError` — `streamablehttp_client()` with `http_client` kwarg
**Severity: CRITICAL — MCP toolsets (knowledge, ticketing) fail to initialize**

```
TypeError: streamablehttp_client() got an unexpected keyword argument 'http_client'
at: livekit/agents/llm/mcp.py:341
```

**Root Cause**: The `agent-worker` Docker container has `mcp==1.11.0` installed (verified via `pip show mcp`). However, `livekit-agents==1.6.3` calls `streamablehttp_client(http_client=...)` at line 341 of `livekit/agents/llm/mcp.py`, and the `http_client` keyword argument was **removed** in `mcp>=1.12`. 

Wait — `mcp==1.11.0` is `<1.12`, so this call SHOULD work. But it's failing anyway.

**Investigation**: The error means the `streamablehttp_client` function (from the `mcp` package) does NOT accept an `http_client` kwarg. This contradicts the assumption that `mcp<1.12` supports this kwarg.

**Possible explanations**:
- **a)** The kwarg was already removed before `1.12` — in `mcp>=1.9` or `>=1.10`. Version `1.11.0` may already have the breaking change.
- **b)** The `streamablehttp_client` signature in `mcp>=1.X` never had `http_client` — the kwarg may have been added by `livekit-agents` but never existed in `mcp`.
- **c)** The kwarg exists in `mcp<1.9` and was removed earlier than `1.12`.

**What's needed**: Determine the **exact last `mcp` version** that accepts `streamablehttp_client(http_client=...)`. The `mcp>=1.0.0,<1.12` pin is too broad — need to narrow to the actual compatible range.

**Symptom**: Triggered twice during `_do_setup` — both MCP toolset initializations fail. The agent continues without MCP tools (no knowledge RAG, no ticketing). Fallback to inline logic only.

**Status**: ❌ **STILL BROKEN** — This was supposed to be fixed by pinning `mcp<1.12`, but `1.11.0` also fails. The pin needs tightening.

---

### Issue 2: Gemini LLM 400 — "deadline too short (5s < 10s minimum)"
**Severity: CRITICAL — Primary LLM completely non-functional**

```
message='gemini llm: client error', status_code=400, retryable=False
body={
  "error": {
    "code": 400,
    "message": "Manually set deadline 5s is too short. Minimum allowed deadline is 10s.",
    "status": "INVALID_ARGUMENT"
  }
}
```

**Root Cause**: The `livekit.plugins.google.llm.LLM` (from `livekit-agents==1.6.3`) sets a **5-second gRPC deadline** when calling the Gemini API via `google-genai`. Google Gemini now requires a **minimum deadline of 10 seconds**, rejecting any request with a shorter deadline.

This is **NOT a model ID issue** — the model `gemini-3.5-flash` is correct. The error is at the transport layer (gRPC deadline), not the model endpoint.

**Symptom**: Every single Gemini call fails with the same 400 error (4+ times in this session). The FallbackAdapter correctly rotates to the next provider (NVIDIA NIM). All LLM responses in this session come from NVIDIA.

**Impact**: 
- Primary LLM completely unusable
- Added latency: Gemini fails → timeout → NVIDIA runs (total ~3s extra per turn)
- The `livekit.agents` recovery mechanism retries Gemini once per call (seen: "switching to next LLM" then "Gemini recovery failed"), doubling the delay

**Status**: ❌ **BLOCKED** — No code change in our repo can fix this. The deadline is hardcoded inside `livekit.plugins.google.llm.LLM` in the `livekit-agents==1.6.3` package. Fix options:
- **Option A**: Upgrade `livekit-agents` to a version where LiveKit fixed the deadline (if exists)
- **Option B**: Monkey-patch `livekit.plugins.google.llm.LLM` to override the deadline
- **Option C**: Remove Gemini from the chain and promote NVIDIA to primary (until google plugin is fixed)

---

### Issue 3: NVIDIA NIM now works ✓
**Severity: NONE — Previously broken, now functional**

```
NvidiaLLM: initialising with model=meta/llama-3.1-8b-instruct endpoint=https://integrate.api.nvidia.com/v1
LLM metrics: model_name=meta/llama-3.1-8b-instruct, model_provider=integrate.api.nvidia.com
    ttft=0.77, prompt_tokens=249, completion_tokens=19, tokens_per_second=24.54
```

**Status**: ✓ **RESOLVED** — The model ID change from `nvidia/nemotron-3-nano-30b-a3b` → `meta/llama-3.1-8b-instruct` fixed the NVIDIA fallback. All LLM calls in this session are served by NVIDIA NIM with good performance (~0.8s TTFT, 25 tokens/s).

**Note**: NVIDIA is now the **de facto primary LLM** because Gemini fails every call. This is a fallback-by-default situation — the agent never uses its actual primary.

---

### Issue 4: STT Deepgram — working correctly ✓
```
STT metrics: model_name=nova-3, model_provider=Deepgram, audio_duration=3.95
```

**Status**: ✓ **RESOLVED** — Deepgram nova-3 transcribes audio correctly. No 404 or 429 errors.

---

### Issue 5: OpenTelemetry Collector not running
**Severity: WARNING — Traces lost but no functional impact**

```
Transient error StatusCode.UNAVAILABLE encountered while exporting traces to localhost:[ID]
Failed to export traces to localhost:[ID], error code: StatusCode.UNAVAILABLE
```

**Root Cause**: The OTEL collector container (`otel-collector`) is not running or is unreachable at `localhost:4317`. Docker `ps` earlier showed it was missing from the container list.

**Status**: ❌ **Non-blocking** — No traces are exported, but calls continue normally.

---

### Issue 6: TTS Output — not verified in this log
**Severity: UNKNOWN**

There are **no TTS-related log lines** in this session output. The session was interrupted early (the `make live-logs` command was canceled). Possible scenarios:
- TTS is working (Cartesia as effective primary since ElevenLabs key is empty)
- TTS is failing silently (no explicit error logging)
- Session ended before TTS output was generated

**Status**: ❓ **Needs verification** — Run a complete session (don't cancel early) to see TTS behavior.

---

### Issue 7: STT end-of-speech vs VAD sync drift
**Severity: MINOR — Speech boundary misalignment**

```
stt end of speech received while vad is still in a speech segment, flushing vad
vad_speech_start_time=1783191024.4435701, flushed=true
```

**Root Cause**: Deepgram's end-of-speech detection disagrees with the local VAD (Silero). Deepgram declares speech ended while VAD still detects voice activity. This causes forced VAD segment flush.

**Symptom**: Triggers twice per call. Causes small audio clipping at sentence boundaries. Not user-perceptible for most normal-speed speech.

**Status**: ⚠ **Known quirk** — STT is cloud-based (Deepgram), VAD is local (Silero). Synchronization drift is expected. Mitigation: increase `vad_min_silence` threshold or switch to STT-only turn detection (already done — `turn_detection="stt"`).

---

### Issue 8: Inference slower than realtime
**Severity: MINOR — Latency spikes during LLM calls**

```
inference is slower than realtime, delay=0.52, 1.13, 0.63, 0.33, 0.31, 0.18, 0.24, 0.49, 0.29, 0.34
```

**Root Cause**: LLM inference (NVIDIA NIM via internet) introduces variable latency. The pipeline processes audio faster than the LLM can generate text, creating a bottleneck. The spike of 1.13s corresponds to the Gemini 400 → NVIDIA fallback transition.

**Status**: ⚠ **Acceptable** — Delays range from 180ms to 1.13s. Average ~500ms. The Gemini 400 fallback adds 1-2s but that's a separate issue (#2). Once Gemini is fixed, inference latency should drop to 200-500ms consistently.

---

### Issue 9: Deprecated APIs
**Severity: INFO — Future incompatibility warning**

```
WARNING: preemptive_generation, turn_detection are deprecated and will be removed in v2.0
WARNING: metrics_collected is deprecated. Use session_usage_updated 
```

**Root Cause**: `livekit-agents==1.6.3` deprecates `turn_detection` + `preemptive_generation` parameters in favor of the unified `turn_handling=TurnHandlingOptions(...)` API. However, `TurnHandlingOptions` may not be available in v1.6.3 (it was introduced later).

**Status**: ⚠ **Needs update before upgrading livekit-agents to v2.0**. Current code works with v1.6.3. Must migrate `session_factory.py` to use the new API before any `livekit-agents>=2.0` upgrade.

---

### Issue 10: OTEL configured twice
**Severity: MINOR — Duplicate initialization**

```
INFO:observability_kit.telemetry:OTel configured for agent-worker -> http://localhost:[ID]  (first)
INFO:observability_kit.telemetry:OTel configured for agent-worker -> http://localhost:[ID]  (second, same pid)
```

**Root Cause**: `observability_kit.telemetry` is called twice during process initialization — once in the main process (pid 156) and once in the agent subprocess (pid 57). Both calls attempt to configure the same OTEL exporter. This may cause resource leaks or conflicts.

**Status**: ⚠ **Cosmetic** — Doesn't break functionality, but indicates subprocess not inheriting OTEL config correctly.

---

## 3. Session Flow Recap

```
1. [OK]       User clicks "Start Call" in browser widget
2. [OK]       Token-service mints LiveKit token (wss://...cloud)
3. [OK]       LiveKit dispatches job to agent-worker (job_id: AJ_sxrRe8osQSEW)
4. [OK]       Agent-worker initializes process (pid 156 → 57 subprocess)
5. [OK]       NVIDIA NIM adapter initialises (model=meta/llama-3.1-8b-instruct)
6. [OK]       Groq adapter initialises (model=llama-3.1-8b-instant)
7. [WARN]     Deprecated API warnings (turn_detection, preemptive_generation)
8. [OK]       Agent session starts, process initialized
9. [WARN]     Adaptive interruption disabled (production mode default)
10. [CRITICAL] MCP TypeError — both MCP toolsets fail to initialize (x2)
11. [OK]      Triage agent enters (language=fr)
12. [OK]      Triage session started
13. [CRITICAL] Gemini LLM 400 — "deadline too short" → primary fails
14. [OK]      NVIDIA NIM activates as fallback → LLM response generated (ttft=0.77s)
15. [WARN]    Inference slower than realtime (x10 due to Gemini retries + NVIDIA calls)
16. [WARN]    OTEL traces export fails (collector unreachable)
17. [OK]      STT Deepgram transcribes audio (nova-3, 3.95s segment)
18. [WARN]    STT/VAD sync drift (end of speech while vad active, x2)
19. [OK]      NVIDIA NIM generates triage greeting (712 tokens, ttft=0.95s)
20. [WARN]    Gemini recovery retries fail again (x2 more 400 errors)
21. [INFO]    Audit trail logs consent event
22. [??]      TTS output — not logged (session interrupted before TTS phase)
23. [CANCEL]  User cancels `make live-logs` (Ctrl-C, exit code 130)
```

---

## 4. Active Provider Chain Status

| Provider | Type | Status | Why |
|----------|------|--------|-----|
| **Gemini 3.5 Flash** | LLM Primary | ❌ BROKEN | gRPC deadline 5s rejected (min 10s), hardcoded in `livekit.plugins.google` |
| **NVIDIA NIM** | LLM Fallback | ✓ ACTIVE | All LLM calls served by NVIDIA after Gemini fails |
| **OpenAI GPT-4o-mini** | LLM Fallback | ⏭ SKIPPED | `OPENAI_ENABLED=false`, skipped in chain |
| **Groq** | LLM Fallback | ⏸ IDLE | NVIDIA succeeds, Groq never reached |
| **Deepgram nova-3** | STT Primary | ✓ OK | Transcribes correctly |
| **Cartesia sonic-2** | TTS (effective primary) | ❓ UNKNOWN | Not logged in this session |
| **ElevenLabs** | TTS (configured primary) | ⏭ SKIPPED | `ELEVEN_API_KEY` empty, skipped in chain |
| **Knowledge MCP** | Tools | ❌ BROKEN | MCP TypeError prevents tool initialization |
| **Ticketing MCP** | Tools | ❌ BROKEN | MCP TypeError prevents tool initialization |
| **Silero VAD** | VAD | ✓ OK | Voice detection works |
| **STT turn detection** | Turn Handling | ✓ OK | `turn_detection="stt"` works (correctly logs "EOU metrics") |

---

## 5. Root Cause Summary Table

| Issue | Root Cause | Location | Fix Type |
|-------|-----------|----------|----------|
| **MCP TypeError** | `mcp==1.11.0` doesn't accept `http_client` kwarg even though `<1.12` | `livekit/agents/llm/mcp.py:341` calling `streamablehttp_client(http_client=...)` | **Pin `mcp` to correct compatible version** (need to identify exact last version with `http_client` support) |
| **Gemini 400** | `livekit.plugins.google.llm.LLM` hardcodes 5s gRPC deadline; Gemini requires ≥10s | `livekit-plugins-google` internal gRPC config | **Upgrade `livekit-agents`** or **monkey-patch deadline** or **demote Gemini** |
| **OTEL unavailable** | OTEL collector container not running | docker-compose infra | **Start otel-collector container** |
| **Deprecated APIs** | `livekit-agents==1.6.3` deprecates `turn_detection` param | `session_factory.py` | **Migrate to `turn_handling=TurnHandlingOptions(...)`** before v2.0 |
| **OTEL double init** | Subprocess re-initializes OTEL that parent already configured | `observability_kit.telemetry` init call site | **Make OTEL init idempotent** or check if already configured |
| **STT/VAD drift** | Cloud STT (Deepgram) vs local VAD (Silero) timing mismatch | `livekit.agents` voice assistant pipeline | **Increase `vad_min_silence`** or accept as known quirk |

---

## 6. Action Items (Priority Order)

### P0 — BLOCKING (session non-functional without fixes)
1. **Fix MCP TypeError** — Identify exact last `mcp` version with `streamablehttp_client(http_client=...)` support and pin to that range (likely `<1.9` or `<1.10`, not `<1.12`)
2. **Fix Gemini 400 deadline** — Options:
   - Upgrade `livekit-agents` to a version with corrected deadline
   - Monkey-patch `google_genai` deadline before LLM init
   - Demote Gemini to fallback and make NVIDIA primary (simplest fix, LLM works now via NVIDIA)

### P1 — IMPORTANT (degraded experience)
3. **Start OTEL collector** — Add to docker-compose and ensure it's always running
4. **Verify TTS output** — Run a full session (don't cancel) and check Cartesia TTS is producing audio

### P2 — NICE TO HAVE 
5. **Fix OTEL double init** — Make telemetry init idempotent
6. **Migrate deprecated APIs** — Switch `turn_detection` → `turn_handling=TurnHandlingOptions(...)` before livekit-agents v2.0 upgrade
7. **Tune VAD/STT sync** — Adjust `vad_min_silence` if drift causes audio cuts