# Version 39 — Cross-Encoder Reranker (RAG Phase 7)

## Summary

Adds a cross-encoder reranker (`jinaai/jina-reranker-v2-base-multilingual`,
~1.1 GB ONNX) that solves a **structural problem** with the bi-encoder relevance
gate: on the real 16-document corpus, the control query scored *higher* than the
correct Arabic answer (0.8411 vs 0.8310), making it provably impossible for any
cosine-threshold gate to separate noise from signal. The cross-encoder reads
query and passage together with full attention, dropping the noise ceiling from
0.84 to ~0.10.

## Changes

### 1. Cross-Encoder Reranker (`services/knowledge-service/src/knowledge_service/reranker.py`, new, 145 lines)

**Why it exists**: On the 16-document corpus the bi-encoder (E5) gave the
control query "how do I fix my washing machine" **0.8411** while the Arabic true
positive scored **0.8310**. The noise outranks the signal. No FLOOR can drop the
noise without dropping Arabic — the two distributions are not merely tight, they
are **inverted**. A bi-encoder compares two independent summaries, so
"troubleshooting prose" looks similar regardless of subject. A cross-encoder
reads text together with full attention and sees that "washing machine" is not
"wifi router".

- Model: `jinaai/jina-reranker-v2-base-multilingual` — the only multilingual
  cross-encoder `fastembed` ships (the 0.08 GB ms-marco models are English-only
  and cannot score French or Arabic at all).
- **~1.11 GB RAM**, runs per candidate — the most expensive component in the
  pipeline, and necessary only because the cheap option is now measurably broken.
- `score(query, documents)` → sigmoid(logit) → 0–1 relevance probability.
  Default threshold: **0.5**. Irrelevant passages land near 0 instead of 0.84.
- Thread-safe lazy load, configurable thread count, `health_check()`.

### 2. Retriever Integration (`services/knowledge-service/src/knowledge_service/retriever.py`)

- `QdrantE5Retriever.search()` **over-fetches** — when the reranker is enabled,
  the dense stage retrieves `KNOWLEDGE_RERANK_CANDIDATES` (default 12) instead
  of `top_k`, because the reranker can only choose from what the bi-encoder
  returned.
- `rerank_passages(query, passages, top_k)` — scores dense hits with the
  cross-encoder, applies the threshold, replaces each passage's `score` with
  the reranker relevance probability (original cosine preserved in
  `metadata["dense_score"]`).
- **No fallback**: on reranker failure, raises `RetrieverUnavailable`. The
  cosine gate is provably broken on this corpus — falling back would feed the
  agent confident noise. An honest 503 makes the agent say it has no
  information; a silent downgrade makes it invent one.

### 3. Boot & Health (`services/knowledge-service/src/knowledge_service/main.py`, `Dockerfile`)

- **Lifespan**: reranker warmed at boot via `health_check()`. The ~1.1 GB load
  cost is never paid on the first caller's question.
- **Health**: `/health` checks `reranker_enabled()` → `get_reranker().health_check()`,
  returning 503 when the reranker is dead.
- **Dockerfile**: reranker model **baked at build time** with a build-time
  health check (`python -c "from knowledge_service.reranker import ..."`).

### 4. Calibration Probe (`scripts/knowledge_score_probe.py`, rewritten)

- Now prints **BOTH** ungated dense scores AND cross-encoder scores for
  identical candidates.
- Side-by-side comparison `rerank=X.XXXX  dense=Y.YYYY (dense#N)` per passage.
- Summary reports **dense noise ceiling**, **rerank noise ceiling**, and the
  **safe threshold window** between the control ceiling and the lowest
  per-language true positive.
- Reports per-language headroom and flags inversion: `DENSE ... <-- INVERTED`
  or `RERANK ... <-- STILL INVERTED`.

### 5. Configuration (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWLEDGE_RERANKER_ENABLED` | `true` | On by default; off means the broken cosine gate |
| `KNOWLEDGE_RERANKER_MODEL` | `jinaai/jina-reranker-v2-base-multilingual` | The cross-encoder |
| `KNOWLEDGE_RERANK_CANDIDATES` | `12` | Recall ceiling AND latency bill |
| `KNOWLEDGE_RERANK_THRESHOLD` | `0.5` | Relevance probability (0-1) |
| `KNOWLEDGE_RERANKER_THREADS` | `0` | 0 = onnxruntime decides |

### 6. Pipeline Audit (`honest_answers.md`, new, 200 lines)

Documents the honest trade-offs of phases 1-7: what is fixed, what is not, what
the latency is, what the reranker costs, and what remains after phase 7.

### Files Changed

| File | Status | Lines |
|------|--------|-------|
| `.env.example` | Modified | +19/-2 |
| `scripts/knowledge_score_probe.py` | Rewritten | ~90 |
| `services/knowledge-service/Dockerfile` | Modified | +1/-0 |
| `services/knowledge-service/src/knowledge_service/main.py` | Modified | +19/-0 |
| `services/knowledge-service/src/knowledge_service/retriever.py` | Modified | +59/-4 |
| `services/knowledge-service/src/knowledge_service/reranker.py` | **New** | 145 |
| `honest_answers.md` | **New** | 200 |
| **Total** | | **~513 added, 48 deleted** |

## Containers & Dependencies

- **knowledge-service** container image now also bakes the reranker model at
  build time (~1.1 GB additional image size).
- **No new Python dependencies** — `TextCrossEncoder` ships with
  `fastembed>=0.8.0` already installed in v36.
- **RAM warning**: the reranker adds ~1.1 GB to the knowledge-service process.
  Ensure the host/container has at least 2 GB available for the service.
- **No LiveKit SDK changes.**

## Testing Notes

- **Reranker health**: call `GET /health` and verify `checks.reranker == "ok"`.
- **Relevance**: run `knowledge_score_probe.py` inside the container and verify
  the rerank noise ceiling is clearly below the true positive scores.
- **Search with reranker**: send queries in EN, FR, AR. Verify that irrelevant
  control queries return `[]` and relevant queries return correct passages.
- **Threshold calibration**: if a language returns false negatives, lower
  `KNOWLEDGE_RERANK_THRESHOLD` based on the probe's per-language report.
- **Latency**: measure `/search` response time — 2-5s expected for 12
  candidates. Tune `KNOWLEDGE_RERANK_CANDIDATES` or `_THREADS` if needed.
- **503 path**: stop the knowledge-service and verify the MCP tool returns `[]`.
