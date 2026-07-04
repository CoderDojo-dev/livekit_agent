# Error Investigation Report — Telecom AI Agent Platform

**Date**: 2026-07-04
**Log Source**: `agent-worker-1`, `token-service-1`
**Session IDs**: `AJ_8Nr74vvxspRJ`, `AJ_AZ7k8wVZKBFq`, `AJ_P8Duc2FzpCvq`

---

## Summary

The agent connects to LiveKit, microphone works, STT (Deepgram nova-3) transcribes audio successfully — but **no LLM generates a response**. Every call fails at the LLM inference layer. All four LLM providers in the `FallbackAdapter` chain fail, causing the agent to become unresponsive. Additionally, MCP server initialization crashes and the turn detection (VAD) model cannot run.

---

## Root Causes — Critical (Must Fix First)

### 1. Gemini Model ID Still References `gemini-2.5-flash-latest` — 404 NOT_FOUND

**Severity**: CRITICAL — blocks all calls
**Error**:
```
models/gemini-2.5-flash-latest is not found for API version v1beta,
or is not supported for generateContent.
Call ModelService.ListModels to see the list of available models
and their supported methods.
```

**Source**: `livekit.plugins.google.llm.LLM` (the LiveKit Google plugin, not the platform's own gemini provider)

**Chain of evidence**:
- `WARNING:livekit.agents:livekit.plugins.google.llm.LLM failed, switching to next LLM`
- `status_code=404, retryable=False`
- `message: 'models/gemini-2.5-flash-latest is not found...'`

**Root cause**: The agent worker is configured to use `gemini-2.5-flash-latest` (the old model ID) instead of `gemini-3.5-flash`. The LiveKit Google LLM plugin reads the model name from the agent's configuration. Even though `prompt.md` requested updating to `gemini-3.5-flash`, the **LiveKit agent configuration** (not the platform's `settings.py`) is what the LiveKit plugin actually uses.

**Where to fix**:
1. `apps/agent-worker/src/config/settings.py` — verify `GEMINI_MODEL=gemini-3.5-flash`
2. `apps/agent-worker/src/providers/llm.py` — verify the LiveKit plugin receives `gemini-3.5-flash` not `gemini-2.5-flash-latest`
3. Any LiveKit agent config files (e.g., `agent_configs/`, `telecom_agent.py`, or wherever the voice agent is initialized) — check for hardcoded `gemini-2.5-flash-latest`
4. The LiveKit Google plugin accepts model IDs — verify it accepts `gemini-3.5-flash` (not `gemini-3.5-flash-latest`)

**Action**: Search entire codebase for `gemini-2.5-flash` and replace with `gemini-3.5-flash`.

---

### 2. Groq Model ID Decommissioned — `llama3-8b-[ID]` No Longer Supported

**Severity**: HIGH — blocks fallback chain
**Error**:
```
The model `llama3-8b-[ID]` has been decommissioned
and is no longer supported.
Please refer to https://console.groq.com/docs/deprecations
for a recommendation on which model to use instead.
```

**Source**: `providers.groq_adapter.GroqLLM`

**Chain of evidence**:
- `INFO:providers.groq_adapter:GroqLLM: initialising with model=llama3-8b-[ID]`
- `status_code=400, retryable=False`

**Root cause**: Groq decommissioned the `llama3-8b-*` model family. The Groq adapter is still configured with the old model ID (`llama3-8b-[ID]`). Groq now recommends `llama-3.1-8b-instant` as the replacement.

**Where to fix**:
- `apps/agent-worker/src/config/settings.py` — set `GROQ_MODEL=llama-3.1-8b-instant` (or verify via Groq deprecations page)
- `.env` — update `GROQ_MODEL` env var
- `apps/agent-worker/src/providers/groq_adapter.py` — verify it reads `GROQ_MODEL` from settings

**Groq recommended replacements** (from Groq deprecations):
- `llama-3.1-8b-instant` — replacement for `llama3-8b-*`
- `llama-3.1-70b-instant` — replacement for larger models

---

### 3. OpenAI API Key Quota Exceeded — 429 Insufficient Quota

**Severity**: HIGH — blocks fallback chain
**Error**:
```
You exceeded your current quota, please check your plan and billing details.
For more information on this error:
https://platform.openai.com/docs/guides/error-codes/api-errors.
```
**Source**: `livekit.plugins.openai.llm.LLM`
**Error code**: HTTP 429

**Root cause**: The OpenAI API key is either:
- Empty (`OPENAI_API_KEY=` in `.env`) — in which case the key should not be enabled
- Has a key but the account has exceeded its quota

**Where to fix**: `.env` — set `OPENAI_ENABLED=false` until a valid OpenAI key with quota is added. The platform should not attempt OpenAI calls if there is no valid key.

---

### 4. NVIDIA NIM Adapter Request Timed Out — Repeatedly

**Severity**: HIGH — blocks fallback chain
**Error**:
```
providers.nvidia_adapter.NvidiaLLM failed, switching to next LLM: Request timed out.
```

**Source**: `providers.nvidia_adapter.NvidiaLLM`

**Chain of evidence**:
- Multiple `WARNING:livekit.agents:providers.nvidia_adapter.NvidiaLLM failed` with `Request timed out`
- `recovery failed: Request timed out`
- Adapter initializes: `INFO:providers.nvidia_adapter:NvidiaLLM: initialising with model=meta/llama-3.1-8b-instruct`

**Root cause**: The NVIDIA NIM endpoint `https://integrate.api.nvidia.com/v1` is timing out. Possible causes:
1. The `NVIDIA_API_KEY` is empty or invalid — if no key is set, the adapter should report `is_available=false` and not be called
2. Network/firewall blocking outbound HTTPS to `integrate.api.nvidia.com` from the container
3. The NVIDIA model ID `meta/llama-3.1-8b-instruct` may not be available under the user's API key
4. The request timeout (default 60s) is too short for the model

**Verification steps**:
1. Check `NVIDIA_API_KEY` is set in `.env`
2. From inside the container, test: `curl -H "Authorization: Bearer $NVIDIA_API_KEY" https://integrate.api.nvidia.com/v1/models`
3. Verify the model `meta/llama-3.1-8b-instruct` is accessible under the key at https://console.nvidia.com/

**Where to fix**:
- `apps/agent-worker/src/providers/nvidia_adapter.py` — ensure `is_available` returns `False` when `api_key` is empty, so the `FallbackAdapter` skips it
- `.env` — add a valid `NVIDIA_API_KEY` if not present
- The adapter logs show it IS initializing, which means a key IS present — but the API is returning timeouts. Check NVIDIA quota/availability

---

### 5. MCP Server Initialization Crashes — `streamablehttp_client()` Version Mismatch

**Severity**: CRITICAL — prevents agent from starting properly
**Error**:
```
TypeError: streamablehttp_client() got an unexpected keyword argument 'http_client'
  File "livekit/agents/llm/mcp.py", line 341, in _streamable_http_with_client
    async with streamable_http_client(
TypeError: streamablehttp_client() got an unexpected keyword argument 'http_client'
```

**Source**: `livekit/agents/llm/mcp.py` → `streamablehttp_client()` from the `mcp` package

**Root cause**: Version incompatibility between `livekit.agents` (v0.x) and the `mcp` Python package. The `mcp` package's `streamablehttp_client()` function signature changed — it no longer accepts an `http_client` keyword argument, but `livekit.agents/llm/mcp.py` is passing it. This is a known breaking change in the `mcp` package.

**The MCP servers affected** (from the error trace):
- `ticketing_glpi` (via `MCPToolset` in agent setup)
- `messaging_gateway` (same)
- `ai-knowledge-rag` (same)

**Where to fix**:
1. Check installed versions: `pip list | grep mcp` inside the agent-worker container
2. Pin the `mcp` package to a compatible version:
   - `mcp<1.12` or the specific version that still accepts `http_client`
   - Or upgrade `livekit.agents` to a version that uses the new `mcp` API
3. Alternatively: check if `MCP_SERVER_URL` environment variables are pointing to the correct MCP server endpoints

**Temporary workaround**: Disable MCP tools in the agent config while fixing the version mismatch. Look for `mcp_servers` or `tools` configuration in the agent worker.

---

## Root Causes — Moderate

### 6. Turn Detection (VAD) — `lk_end_of_utterance_multilingual` No Inference Executor

**Severity**: MODERATE — causes noisy errors but STT still works
**Error**:
```
RuntimeError: inference of lk_end_of_utterance_multilingual failed: no inference executor
WARNING:livekit.agents:inference request received but no inference executor
```

**Source**: `livekit/plugins/turn_detector/multilingual.py` → `lk_end_of_utterance_multilingual`

**Root cause**: The LiveKit turn detection model (`lk_end_of_utterance_multilingual`) requires a local inference executor (likely a local model or LiveKit's own inference runtime). It is not available in the current setup. This is non-fatal — STT still works (Deepgram nova-3 is operating correctly), but the turn detection model throws continuous errors.

**Likely cause**: LiveKit Cloud does not provide local inference executors by default. The turn detection runs inside the LiveKit agent process and needs either:
- A local VAD model (Silero VAD) — but the `multilingual` turn detector may conflict
- The agent may be misconfigured to use a cloud inference path for turn detection

**Where to fix**:
- `apps/agent-worker/src/providers/` — check which VAD/turn detector is configured
- The agent logs show `"model_name": "multilingual", "model_provider": "livekit"` for EOU metrics — this confirms the LiveKit-provided multilingual turn detector is active
- In the agent config, ensure `turn_detection` or `turn_handling` is set to use a provided executor, or switch to Silero VAD
- This is a LiveKit-specific configuration — check `livekit.agents.voice.agent_config` or similar

**Note**: This error recurs every few seconds per session. It is noise in the logs and does not cause call failure directly, but it indicates a misconfiguration.

---

### 7. OpenTelemetry Collector Not Running — Traces Export Fails

**Severity**: LOW — observability only
**Error**:
```
ERROR:opentelemetry.exporter.otlp.proto.grpc.exporter:
Failed to export traces to localhost:[ID], error code: StatusCode.UNAVAILABLE
WARNING:opentelemetry.exporter.otlp.proto.grpc.exporter:
Transient error StatusCode.UNAVAILABLE encountered while exporting traces to localhost:[ID], retrying in 1.12s.
```

**Source**: `opentelemetry.exporter.otlp.proto.grpc.exporter`

**Root cause**: The OpenTelemetry collector (OTEL endpoint `localhost:[ID]` — likely port 4317 or 4318) is not running. The `observability_kit` package is configured to export traces to a local OTEL collector, but no collector is present.

**Where to fix**:
- The infra docker-compose has an `otel` service — verify it is running: `docker compose -f infra/docker-compose/docker-compose.yml ps`
- If using the full Helm chart, ensure the OTEL collector is deployed
- If OTEL is not needed for development, disable it in `apps/agent-worker/src/config/settings.py` or via `OTEL_ENABLED=false`

---

### 8. LiveKit FFI Room Event Timeout

**Severity**: MODERATE — causes agent process to crash/restart
**Error**:
```
ERROR:livekit:livekit_ffi::server::room:256:livekit_ffi::server::room
- timed out waiting for ReadyForRoomEventRequest after ConnectCallback (room_handle=7)
FFI Panic: invalid request: timed out waiting for ReadyForRoomEventRequest after ConnectCallback
ERROR:livekit.agents:process exited with non-zero exit code -15
```

**Source**: `livekit_ffi` (Rust FFI bridge between LiveKit agent and LiveKit runtime)

**Root cause**: The LiveKit agent's FFI connection to the LiveKit room timed out. This typically happens when:
1. The LiveKit server (Cloud or self-hosted) takes too long to send the initial room events
2. The agent process was killed (exit code -15 = SIGTERM) after this panic

**Important**: This error caused the first agent session (`AJ_AZ7k8wVZKBFq`) to crash with exit code -15. The second session (`AJ_P8Duc2FzpCvq`) appeared to start successfully.

**Where to fix**:
- The LiveKit Cloud URL being used is: `wss://telecom-ai-agent-platform-nlcenyl7.livekit.cloud`
- This is expected behavior when the agent starts before the room is fully ready
- If it happens frequently, increase LiveKit room event timeout in the agent config
- Exit code -15 suggests the process was killed externally — check if a supervisor is restarting the agent

---

### 9. Memory Warning — Agent Worker Above 1GB

**Severity**: LOW — warning, not fatal
**Error**:
```
WARNING:livekit.agents:job process memory usage is above the warning threshold
memory_usage_mb: 1041.1, memory_warn_mb: 1000, growth_memory_mb: 635.9
WARNING:livekit.agents:job process memory usage is above the warning threshold
memory_usage_mb: 1106.7, memory_warn_mb: 1000, growth_memory_mb: 701.6
```

**Source**: LiveKit agent job process

**Root cause**: The agent-worker subprocess grows to ~1GB over ~5 minutes of operation. This is expected for a voice agent with multiple LLM providers loaded (4 LLM providers + STT + TTS + turn detection + MCP clients). Not immediately fatal but indicates memory management should be reviewed.

---

### 10. Deprecated LiveKit API Warnings

**Severity**: INFO — not errors
**Warnings to ignore**:
```
WARNING:livekit.agents:preemptive_generation, turn_detection are deprecated
and will be removed in v2.0. Use turn_handling=TurnHandlingOptions(...) instead

WARNING:livekit.agents:metrics_collected is deprecated.
Use session_usage_updated for usage tracking and
ChatMessage.metrics for per-turn latency.
```

**Action**: These are informational deprecation warnings from LiveKit. Update to the v2 API when upgrading `livekit.agents`.

---

## LLM Fallback Chain — Full Failure Analysis

The log confirms the complete fallback chain was tried and all failed:

```
all LLMs failed:
1. livekit.plugins.google.llm.LLM         → 404 (gemini-2.5-flash-latest not found)
2. providers.nvidia_adapter.NvidiaLLM     → Request timed out
3. livekit.plugins.openai.llm.LLM          → 429 insufficient_quota
4. providers.groq_adapter.GroqLLM          → 400 model_decommissioned (llama3-8b)
```

This confirms that **all four LLM providers are non-functional**, which is why no voice response was generated. The STT (Deepgram nova-3) worked fine — the caller's speech was transcribed correctly (`audio_duration: 4.3`, `5.0`, `5.05`), but no LLM could generate a response.

---

## What IS Working

| Component | Status | Evidence |
|---|---|---|
| LiveKit connection | OK | Room connected, participant_connected events |
| Microphone/audio | OK | `local_track_published`, `microphone_enabled` |
| Deepgram STT (nova-3) | OK | `STT metrics model_name=nova-3 model_provider=Deepgram` with audio_duration captured |
| Token service | OK | `GET /health 200 OK` |
| Agent process startup | OK | `process initialized`, `triage agent entered language=fr` |
| TTS (ElevenLabs) | OK (no audio generated due to LLM failure) | `resampling livekit.plugins.elevenlabs.tts.TTS` |

---

## Priority Fix Order

### IMMEDIATE (blocks all calls)
1. **Fix Gemini model ID** — replace all `gemini-2.5-flash-latest` → `gemini-3.5-flash` in the codebase
2. **Fix MCP version mismatch** — pin `mcp<1.12` or find compatible versions with `livekit.agents`

### HIGH (blocks fallback chain)
3. **Fix Groq model** — replace decommissioned `llama3-8b-*` with `llama-3.1-8b-instant`
4. **Disable or fix OpenAI** — set `OPENAI_ENABLED=false` until a valid key with quota is available
5. **Debug NVIDIA NIM timeout** — verify `NVIDIA_API_KEY` is valid and the model is accessible; ensure `is_available=false` when no key is set

### MEDIUM
6. **Configure Turn Detection properly** — resolve `lk_end_of_utterance_multilingual no inference executor` or switch to Silero VAD
7. **Start OTEL collector** — or disable OTEL export to clean up logs

### LOW
8. **Memory optimization** — investigate agent-worker subprocess memory growth
9. **LiveKit FFI timeout** — investigate if agent restart is caused by external kill or genuine timeout

---

## Files to Investigate

| File | What to look for |
|---|---|
| `apps/agent-worker/src/config/settings.py` | `GEMINI_MODEL`, `GROQ_MODEL`, `NVIDIA_API_KEY`, `OPENAI_ENABLED` |
| `apps/agent-worker/src/providers/llm.py` | How Gemini is initialized for LiveKit plugin |
| `apps/agent-worker/src/providers/nvidia_adapter.py` | `is_available` property, timeout value |
| `apps/agent-worker/src/providers/groq_adapter.py` | Model name from settings |
| `apps/agent-worker/src/config/language_presets.py` | The 4-key fix from previous session |
| `apps/agent-worker/agent.py` or `apps/agent-worker/main.py` | Where LiveKit agent is configured (model names, turn detection, MCP tools) |
| `.env` | All API keys and `*_ENABLED` flags |
| `pyproject.toml` (agent-worker) | `mcp` and `livekit.agents` version pins |

---

## Environment Variable Audit

| Variable | Current State | Should Be |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash-latest` (wrong) | `gemini-3.5-flash` |
| `GROQ_MODEL` | `llama3-8b-[ID]` (decommissioned) | `llama-3.1-8b-instant` |
| `OPENAI_API_KEY` | empty or quota exceeded | empty → `OPENAI_ENABLED=false` |
| `NVIDIA_API_KEY` | appears to be set but timing out | verify key is valid |
| `OPENAI_ENABLED` | should be `false` | `false` until key fixed |
| `NVIDIA_ENABLED` | should be `true` if key valid | `true` |
| `GROQ_ENABLED` | should be `true` | `true` |
| `DEEPGRAM_API_KEY` | set, STT works | keep as-is |

---

## Verification Commands

```bash
# After fixes, rebuild and verify:
make rebuild

# Check Gemini model directly (from container):
docker exec -it agent-worker-1 python -c "
from livekit.plugins.google.llm import LLM
print(LLM.__init__.__doc__)
"

# Check Groq available models:
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | python -m json.tool

# Check NVIDIA available models:
curl https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_API_KEY" | python -m json.tool

# Check MCP version:
docker exec -it agent-worker-1 pip list | grep mcp

# Verify all providers:
docker exec -it agent-worker-1 python -c "
from apps.agent_worker.src.config import settings
print('GEMINI_MODEL:', settings.GEMINI_MODEL)
print('GROQ_MODEL:', settings.GROQ_MODEL)
print('NVIDIA_API_KEY set:', bool(settings.nvidia_api_key))
print('OPENAI_ENABLED:', settings.OPENAI_ENABLED)
"
```