# version_41 — RAG Phase 8.1: Three-Layer Relevance Gate + Agent Persona Updates

## What's New

### 1. Three-Layer Relevance Gate (knowledge-service)
- **Dense cosine FLOOR** (existing, 0.82) — cheap first-pass filter
- **BM25 lexical co-gate** (`KNOWLEDGE_SPARSE_MIN=0.0`, disabled by default) — kills keyword-absent French noise at ~0 ms
- **Small CE gate** (`KNOWLEDGE_CE_THRESHOLD=0.30`) — new `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (~118 MB, ONNX-quantized) runs on ≤12 survivors, ~80-150 ms per query
- CE gate **degrades gracefully**: on failure falls back to dense+lexical result (no 503), lives outside the readiness gate
- `/health` endpoint reports CE gate readiness separately (`"warming"` / `"ok"` / `"disabled"`); excluded from the readiness gate calculation
- Background warmup thread (non-blocking lifespan start)

### 2. Agent Persona Knowledge Updates
- `KNOWLEDGE_ABSTENTION_RULE` appended to triage, billing, and technical agents: forces agents to answer only from retrieved passages and reply _"Je n'ai pas cette information."_ when passages don't answer
- `base_agent.py`: `knowledge_search()` tool updated with name-based persona parameter (cleaner separation)

### 3. Container & Configuration Changes
- **Dockerfile** (`services/knowledge-service/Dockerfile`):
  - `torch==2.2.2` CPU pre-installed (before sentence-transformers) — avoids pulling ~2 GB CUDA libs, keeps image lightweight
  - `numpy>=1.26,<2` pin — torch 2.2.2 CPU was compiled against numpy 1.x ABI
  - `HF_HOME=/opt/models` env var for HF model caching
  - CE gate model NOT pre-baked (downloads at runtime via lazy loading — HuggingFace Hub is unreliable during Docker builds)
  - Healthcheck start-period reduced to 30s (no CE model to wait for)
- **docker-compose.apps.yml** (`infra/docker-compose/docker-compose.apps.yml`):
  - `HF_HOME` env var added to knowledge-service container
  - `OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4` — cap torch/numpy CPU threads (more reliable than `set_num_threads()` alone)
  - New `knowledge-models` Docker volume for persisting model cache across container recreations (CE model survives `up -d` recreations)
- **pyproject.toml** (`services/knowledge-service/pyproject.toml`):
  - `sentence-transformers==3.3.1` added (CE gate dependency)
  - `huggingface-hub==0.26.5` added (model download)
  - `numpy>=1.26,<2` pin added
- **`.env.example`**: new config keys: `KNOWLEDGE_SPARSE_MIN`, `KNOWLEDGE_CE_GATE_ENABLED`, `KNOWLEDGE_CE_MODEL`, `KNOWLEDGE_CE_THRESHOLD`, `KNOWLEDGE_CE_MAX_CANDIDATES`

### 4. Calibration Probe Updated
- `scripts/knowledge_score_probe.py` rewritten for 3-layer gate calibration: outputs markdown table with `dense_top1 | max_bm25 | ce_top1 | gated_verdict | expected | PASS?`
- Includes 10 true-positive (TP) queries and 8 noise queries (inverted noise gone after CE gate)
- Reports calibration windows: lowest TP vs highest noise at each layer

## Calibration Results
- **True positives gated**: 9/10 (1 FN: `délai de rétractation` — corpus lacks the document; CE correctly dropped it)
- **Noise queries gated**: 7/8
- **Latency**: warm p95 200 ms (CE gate adds ~80-150 ms on ≤8 survivors)
- **CE gate fixes same-language inversion**: noise "recrutement Tunisie Telecom" dense 0.9334 → CE 0.0646; TP "roaming international" dense 0.8493 → CE 0.4167

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `services/knowledge-service/src/knowledge_service/ce_gate.py` | NEW | SmallCrossEncoderGate class |
| `services/knowledge-service/src/knowledge_service/retriever.py` | MODIFIED | 3-layer gate pipeline |
| `services/knowledge-service/src/knowledge_service/main.py` | MODIFIED | CE gate warmup + health endpoint |
| `apps/agent-worker/src/agents/base_agent.py` | MODIFIED | KNOWLEDGE_ABSTENTION_RULE + knowledge_search update |
| `apps/agent-worker/src/agents/triage_agent.py` | MODIFIED | Abstention rule appended |
| `apps/agent-worker/src/agents/billing_agent.py` | MODIFIED | Abstention rule appended |
| `apps/agent-worker/src/agents/technical_agent.py` | MODIFIED | Abstention rule appended |
| `services/knowledge-service/Dockerfile` | MODIFIED | torch CPU, numpy<2, HF_HOME |
| `infra/docker-compose/docker-compose.apps.yml` | MODIFIED | HF_HOME, OMP_NUM_THREADS, knowledge-models volume |
| `services/knowledge-service/pyproject.toml` | MODIFIED | sentence-transformers + numpy<2 deps |
| `.env.example` | MODIFIED | CE gate config keys |
| `scripts/knowledge_score_probe.py` | MODIFIED | 3-layer calibration |
| `RAG_PHASE8_1_REPORT.md` | NEW | Full calibration report |
| `honest_answers.md` | DELETED | Legacy file |
