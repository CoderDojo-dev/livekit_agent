# version_15 — Per-Job Memory Probe with tracemalloc + psutil

## Purpose
Add real-time memory diagnostic logging to identify the source of the 854MB RSS growth observed during dead calls (version_09 logs). The probe logs process RSS, Python heap current/peak, and top 5 allocation sites every 30 seconds per job, enabling root-cause analysis of memory leaks without attaching external profilers.

## Major Changes

### 1. Memory Probe Task (`_mem_probe`)
- **Startup**: `tracemalloc.start(25)` at module import (captures 25 stack frames per allocation)
- **Per-job task**: `asyncio.create_task(_mem_probe())` inside `entrypoint()`
- **Logging cadence**: Every 30 seconds, logs at `WARNING` level to the `memprobe` logger
- **Metrics reported**:
  - `SYSTEM_RSS_MB` — process RSS from `psutil.Process(os.getpid()).memory_info().rss`
  - `PYTHON_CUR_MB` — current Python heap size from `tracemalloc.get_traced_memory()`
  - `PYTHON_PEAK_MB` — peak Python heap size since `tracemalloc.start()`
  - `TOP_ALLOCS` — top 5 allocation sites by size (filename:line=sizeKB)
- **Shutdown**: Cancelled via `ctx.add_shutdown_callback(_stop_mem_probe)`
- **Error handling**: Any exception in the probe is caught and logged, never crashes the job

### 2. Dependency Change
- **Removed**: `python-dotenv==1.0.1` (no longer a direct dependency — env vars loaded by livekit-agents or docker-compose)
- **Added**: `psutil>=5.9` (cross-platform process/ system monitoring)

## Files / Modules Affected (2 files)

| File | Change |
|------|--------|
| `apps/agent-worker/src/server.py` | +39/-0: `_mem_probe()`, `tracemalloc.start()`, `_stop_mem_probe()` shutdown callback |
| `apps/agent-worker/pyproject.toml` | +1/-1: `python-dotenv==1.0.1` → `psutil>=5.9` |

## Differences from version_14

| Aspect | version_14 | version_15 |
|--------|-----------|-----------|
| Memory diagnostics | None | Per-job probe: RSS + Python heap + top 5 allocs every 30s |
| Dependency | `python-dotenv==1.0.1` | `psutil>=5.9` |
