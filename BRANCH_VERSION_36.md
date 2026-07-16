# Version 36 — Local ONNX Embeddings + Qdrant Bootstrap + Container Model Baking

## Summary

Replaces the hosted OpenAI embedding API (`text-embedding-3-small`) with a
**local, quantized, CPU-only ONNX model** (`intfloat/multilingual-e5-small` via
`fastembed`). No API key, no quota, no rate limit, no GPU required. Arabic,
French, and English share one aligned vector space, so a French question can
retrieve an English procedure without translation. Model weights are baked into
the container image at build time — cold start is deterministic and the service
works without internet access.

## Changes

### 1. Container Build & Deployment

**`services/knowledge-service/Dockerfile`:**
- ONNX weights downloaded and verified **at build time** via
  `get_embedder().health_check()` — broken images fail at `docker build`, not at
  runtime.
- Environment variables `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`,
  `EMBEDDING_CACHE_DIR` set as `ENV` in the image.
- `HEALTHCHECK` now uses `--start-period=60s` to cover the ONNX warm-up, and
  `/health` is a real readiness probe (not a liveness lie): it checks the model
  loads and the Qdrant collection exists with matching dimension/distance,
  returning 503 on mismatch.

**`infra/docker-compose/docker-compose.apps.yml`:**
- Pins `EMBEDDING_CACHE_DIR: "/opt/models"` at the container level so a
  host-oriented `.env` cannot point the service at a path that doesn't exist
  inside the image.

### 2. Dependencies (`services/knowledge-service/pyproject.toml`)

- `qdrant-client==1.12.1` moved from `[project.optional-dependencies]` to core
  dependencies (it is always required now).
- `fastembed==0.8.0` added — provides the ONNX runtime and model loading for
  local CPU-based embeddings.
- New console script: `knowledge-bootstrap-qdrant` — runs
  `knowledge_service.qdrant_store:bootstrap()` to idempotently create and verify
  the Qdrant collection and payload indexes.

### 3. New Modules

**`services/knowledge-service/src/knowledge_service/embeddings.py`** (252 lines):
- `LocalEmbedder` — thread-safe, lazy-loaded ONNX session via `fastembed.TextEmbedding`.
- Supports asymmetric E5 prefixes (`query:` / `passage:`) for correct retrieval.
- Validates every emitted vector against the configured dimension — raises
  `EmbeddingError` instead of returning silently bad vectors.
- `health_check()` — proves the model loads and produces the correct dimension.

**`services/knowledge-service/src/knowledge_service/qdrant_store.py`** (159 lines):
- `ensure_collection()` — idempotent bootstrap: creates collection + payload
  indexes (language, document_type, source, active) if absent.
- `verify_collection()` — gate that stops a dimension/distance mismatch from
  being discovered later as silently bad retrieval. Checks vector size, distance
  metric, and payload schema.
- `bootstrap()` — console-script entrypoint for `knowledge-bootstrap-qdrant`.

### 4. Entrypoint (`services/knowledge-service/src/knowledge_service/main.py`)

- Added `lifespan` handler that warms the ONNX session at boot (first caller
  question should not pay the model-load cost).
- `/health` endpoint rewritten as a **real readiness probe**: validates
  embedder (model loads, correct dimension) + Qdrant collection (exists,
  correct dimension, cosine distance). Returns `503` on any failure with
  per-check details.
- `/search` now supports multilingual queries (no longer "English only").

### 5. Embedding Configuration (`.env.example`)

- `EMBEDDING_MODEL` changed from `text-embedding-3-small` (OpenAI API) to
  `intfloat/multilingual-e5-small` (local ONNX).
- Added `EMBEDDING_DIMENSIONS=384`, `EMBEDDING_CACHE_DIR=/opt/models`,
  `QDRANT_TIMEOUT_S=10`.

### 6. Startup Commands (`commands.md`)

- New document at project root containing all make commands, docker-compose
  commands, service ports, dashboard frontend commands, database operations,
  and troubleshooting.

### Files Changed

| File | Status | Lines |
|------|--------|-------|
| `.env.example` | Modified | +8/-1 |
| `infra/docker-compose/docker-compose.apps.yml` | Modified | +3/-0 |
| `services/knowledge-service/Dockerfile` | Modified | +14/-2 |
| `services/knowledge-service/pyproject.toml` | Modified | +10/-5 |
| `services/knowledge-service/src/knowledge_service/main.py` | Modified | +67/-5 |
| `services/knowledge-service/src/knowledge_service/embeddings.py` | **New** | 252 |
| `services/knowledge-service/src/knowledge_service/qdrant_store.py` | **New** | 159 |
| `services/knowledge-service/scripts/rag_embedding_ab_check.py` | **New** | ~120 |
| `commands.md` | **New** | ~260 |
| `results.md` | **New** | 43 |
| **Total** | | **~929 added, 14 deleted** |

## Containers & Dependencies

- `knowledge-service` container image now **bakes model weights at build time**
  (image size increases by ~80 MB for the ONNX model).
- `fastembed==0.8.0` added as core dependency.
- `qdrant-client==1.12.1` promoted from optional to core.
- No LiveKit SDK version changes.
- **Required action**: rebuild the knowledge-service image after deploying this
  version:
  ```
  make rebuild
  ```
  Or manually:
  ```
  docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml build knowledge-service
  ```

## Database / Qdrant

- If a Qdrant collection exists with a different dimension or distance metric,
  `verify_collection()` will return 503 until the collection is recreated.
- Existing vectors from the old model are **not compatible** with `e5-small`:
  recreate the collection and re-ingest.
- Bootstrap the collection:
  ```
  knowledge-bootstrap-qdrant
  ```
  Or inside the container it runs automatically on first health check.

## Testing Notes

- **Embedding**: verify `get_embedder().embed(["test"], "query")` returns a
  384-dimensional vector. Verify E5 prefixes are correctly prepended.
- **Qdrant bootstrap**: run `knowledge-bootstrap-qdrant` and confirm the
  collection is created with 384 dims, cosine distance, and payload indexes.
- **Health probe**: call `GET /health` — should return `{"status": "ok"}` with
  model name, dimensions, collection name, and points count. With Qdrant down,
  should return 503.
- **Search**: send a multilingual query (FR/AR/EN) to `POST /search` and confirm
  results are relevant.
