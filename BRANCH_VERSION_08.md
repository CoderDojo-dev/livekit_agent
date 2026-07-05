# version_08 — Agent-Worker Production Patch Set

## Purpose
Resolve six critical production issues in the agent-worker voice pipeline that caused calls to fail silently (no TTS audio, zero LLM responses, instant job crashes) and eliminate two observability-related regressions (OTel memory leak, dead log handlers).

## Major Changes

### 1. Cartesia TTS Model Migration
- **Model**: `sonic-2` → `sonic-3` (sonic-2 was retired by Cartesia on 2026-06-01)
- **Language param**: Passed to `cartesia.TTS(language=...)` for proper phoneme accenting
- **Removed**: `language=` kwarg from `elevenlabs.TTS()` (plugin 1.6.3 raises `TypeError`)
- **New GeminiTTS fallback**: 4th TTS layer via `google.beta.GeminiTTS` (key-gated on `GOOGLE_API_KEY`)

### 2. MCP Dependency Fix
- **Constraint**: `mcp>=1.9,<1.10` → `mcp>=1.24,<2` (matches livekit-agents 1.6.3 metadata)
- **Extras removed**: `livekit-agents[azure,cartesia,...]==1.6.3` → base `livekit-agents==1.6.3` + individual `livekit-plugins-*>=1.6.3` dependencies (avoids pip extras self-conflict)

### 3. Turn-Detector Crash Fix
- **Root cause**: `register_inference_runners()` was never called in the main process; job subprocesses crashed with "no inference executor"
- **Fix**: Called at module import in `server.py` via `providers/turn_detection.py`
- **New `build_turn_detector()`**: Reads `TURN_DETECTION_MODE` from settings (`stt`, `vad`, `multilingual`)

### 4. Event Handler Migration
- **Old (dead) event names**: `user_speech_committed`, `agent_speech_committed`, `function_calls_collected`, `function_calls_finished`
- **New (verified 1.6.3) events**: `user_input_transcribed`, `conversation_item_added`, `function_tools_executed`

### 5. OTel Memory Leak Fix
- **Problem**: `configure_tracer("agent-worker")` was called per-job, stacking OpenTelemetry tracers
- **Fix**: Moved to module-level — runs once per process, never per-job

### 6. NVIDIA / Groq Adapter Timeout Fix
- **Bug**: `client_kwargs={"timeout": httpx.Timeout(...)}` — `openai.LLM.__init__` does not accept `client_kwargs`
- **Fix**: Passed as direct `timeout=httpx.Timeout(timeout, connect=10.0)` kwarg

### 7. Azure TTS Constructor Fix
- **Bug**: `azure.TTS(api_key=...)` — plugin constructor uses `speech_key`, not `api_key`
- **Fix**: Changed to `azure.TTS(speech_key=...)`

## Files / Modules Affected (17 files)

| File | Change |
|------|--------|
| `.env.example` | 7 key updates (sonic-3, GeminiTTS, turn_detection_mode, job_memory_warn_mb) |
| `apps/agent-worker/pyproject.toml` | mcp>=1.24,<2; pydantic>=2.11.0,<3; plugins as direct deps |
| `apps/agent-worker/src/config/settings.py` | New fields for GeminiTTS, turn_detection_mode, job_memory_warn_mb |
| `apps/agent-worker/src/providers/tts.py` | 4-layer TTS chain (Cartesia → ElevenLabs → Azure → GeminiTTS) |
| `apps/agent-worker/src/providers/nvidia_adapter.py` | timeout=httpx.Timeout(...) direct kwarg |
| `apps/agent-worker/src/providers/groq_adapter.py` | Same timeout fix |
| `apps/agent-worker/src/providers/turn_detection.py` | register_inference_runners() + configurable turn detection |
| `apps/agent-worker/src/providers/session_factory.py` | Updated build_tts(settings) call |
| `apps/agent-worker/src/server.py` | OTel + inference runners at module init; new event handlers |
| `apps/agent-worker/src/mcp_clients/knowledge_toolset.py` | Removed streamable_http shim |
| `apps/agent-worker/src/mcp_clients/ticketing_toolset.py` | Removed streamable_http shim |
| `apps/token-service/pyproject.toml` | pydantic>=2.11.0,<3 |
| `services/context-service/pyproject.toml` | pydantic>=2.11.0,<3 |
| `services/policy-service/pyproject.toml` | pydantic>=2.11.0,<3 |
| `services/execution-service/pyproject.toml` | pydantic>=2.11.0,<3 |
| `services/notification-service/pyproject.toml` | pydantic>=2.11.0,<3 |
| `infra/docker-compose/docker-compose.apps.yml` | Docker-DNS overrides for agent-worker |

## Breaking Changes & Migration Notes

- **pydantic bump**: All services now require `pydantic>=2.11.0,<3` (was `==2.10.4`). Required by `mcp>=1.24`.
- **livekit-agents extras removed**: If you install agent-worker directly, you now need `livekit-agents==1.6.3` + individual `livekit-plugins-*>=1.6.3` packages. `pip install -e .` handles this automatically.
- **Event handlers renamed**: Any custom code listening on `user_speech_committed`, `agent_speech_committed`, `function_calls_collected`, `function_calls_finished` must migrate to `user_input_transcribed`, `conversation_item_added`, `function_tools_executed`.
- **server.py entrypoint signature**: `configure_tracer("agent-worker")` removed from inside `entrypoint()` — it now runs at module import. No change needed for external callers.
- **`.env.example`**: Requires updating existing `.env` files with new keys (`GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`, `TURN_DETECTION_MODE`, `JOB_MEMORY_WARN_MB`) or accepting defaults.

## Differences from version_07

| Aspect | version_07 | version_08 |
|--------|-----------|-----------|
| Cartesia model | sonic-2 (retired) | sonic-3 |
| MCP SDK | mcp>=1.9,<1.10 | mcp>=1.24,<2 |
| TTS layers | ElevenLabs + Cartesia + Azure | Cartesia + ElevenLabs + Azure + GeminiTTS |
| pydantic | ==2.10.4 (all services) | >=2.11.0,<3 (all services) |
| livekit-agents dep | Extras-based | Base + explicit plugin deps |
| Turn detection | STT only (hardcoded) | Configurable (stt/vad/multilingual) |
| OTel configuration | Per-job (leaking) | Module-level (once) |
| Event handlers | 4 old deprecated names | 3 verified 1.6.3 names |
| NVIDIA/Groq timeout | Unwired (silently dropped) | wired via timeout=httpx.Timeout |
| Azure TTS param | api_key= (crashes) | speech_key= |
| streamable_http shim | Present (legacy compat) | Removed |
| Docker DNS overrides | Missing | Added for all service/MCP URLs |
