# Version 40 — Hybrid Dense + BM25 Sparse + RRF Fusion (RAG Phase 8)

## Summary

Retires the 1.1 GB cross-encoder reranker (Phase 7) from the realtime path due
to OOM crashes, 2–5s latency, and French false negatives. Replaces it with
**hybrid retrieval**: dense E5-small as the relevance gate, BM25 sparse for
keyword precision, and Reciprocal Rank Fusion (RRF) for ranking. Latency drops
from 2–5s to **~80ms**, container build time drops to **103s**, and 1.1 GB of
RAM is freed. The corpus is migrated to **100% French-native** content,
eliminating the cross-lingual inversion at the source.

## Changes

### 1. Corpus Migrated to French (`services/knowledge-service/src/knowledge_service/corpus.py`)

All 5 documents translated from English to French:
- Forfait Flexi postpaid (offer)
- Activer l'itinérance internationale (roaming procedure)
- Les données mobiles ne fonctionnent pas (FAQ data troubleshooting)
- Facture et cycle de facturation (FAQ billing)
- Changer de forfait mobile (plan change procedure)

The cross-lingual inversion problem (Phase 6-7) is eliminated at the source:
same-language E5-small similarity is high and well-separated. A
`KNOWLEDGE_DEFAULT_LANGUAGE=fr` filter prevents cross-lingual noise from
leaking in.

### 2. Hybrid Retrieval Pipeline (`services/knowledge-service/src/knowledge_service/retriever.py`)

**Dense E5 (relevance gate):**
- `QdrantE5Retriever.search()` queries the named `dense` vector with
  `score_threshold = FLOOR` (0.82). Passages below the floor are dropped.
- The honest "no answer -> []" guarantee is preserved: if dense returns nothing,
  nothing is returned — sparse-only noise cannot leak through.

**BM25 sparse (keyword precision):**
- `LocalSparseEmbedder` via `fastembed.SparseTextEmbedding` (model:
  `Qdrant/bm25`, tiny, no weights to download of note).
- Queries the named `bm25` sparse vector with IDF modifier.

**RRF fusion (Reciprocal Rank Fusion):**
- Rank-based — needs no score normalization across cosine (~0.8-1.0) and BM25
  (~0-40). `RRF_K=60` (literature default).
- Original dense cosine preserved in `metadata["dense_score"]`.

### 3. Named Vectors in Qdrant (`services/knowledge-service/src/knowledge_service/qdrant_store.py`)

- Collection now uses **named vectors**: `dense` (384d cosine) + `bm25`
  (sparse IDF). The old unnamed single-vector collection is incompatible.
- `verify_collection()` checks for both named vectors and raises a clear error
  (with remediation instructions) if the old format is detected.
- New script `scripts/recreate_collection_fr.py` drops the old collection and
  recreates it with the named-vector schema.

### 4. Embeddings with Sparse + LRU Cache (`services/knowledge-service/src/knowledge_service/embeddings.py`)

- **`LocalSparseEmbedder`** — BM25 sparse vectors via fastembed. Thread-safe
  lazy load, health_check().
- **LRU query cache** (default 256 entries) on `embed_query()` — repeated FAQ
  questions on a voice line skip re-embedding. Cache key is the stripped query
  text; values are tuples (hashable) converted back to lists on read.

### 5. Ingestion + Outbox (`services/knowledge-service/src/knowledge_service/ingestion.py`, `sync_worker.py`)

- `ingest_object()` now embeds BOTH dense + sparse vectors and stores both in
  the Qdrant point under named keys.
- `_upsert_points()` uses `PointStruct` with `{DENSE_VECTOR_NAME: dense_vec,
  SPARSE_VECTOR_NAME: SparseVector(...)}`.
- Outbox drain (`_apply_upsert`) also embeds and stores both vectors.

### 6. Container & Dependencies (`Dockerfile`, `.env.example`)

- **Dockerfile**: bakes the tiny sparse BM25 model instead of the 1.1 GB
  cross-encoder. Build-time health check verifies the sparse embedder.
  Container build time: ~103s.
- **No new Python dependencies** — `SparseTextEmbedding` ships with
  `fastembed >= 0.8.0` already installed.
- **Cross-encoder reranker** (Phase 7): default set to `KNOWLEDGE_RERANKER_ENABLED=false`.
  Kept for offline A/B evaluation. NOT on the realtime readiness path.

### 7. New Configuration (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWLEDGE_SCORE_FLOOR` | `0.82` | Dense cosine relevance gate (passages below are dropped) |
| `KNOWLEDGE_RELATIVE_CUTOFF` | `0.90` | Relative cutoff (superseded by RRF) |
| `KNOWLEDGE_HYBRID_ENABLED` | `true` | Enable dense + BM25 + RRF hybrid retrieval |
| `KNOWLEDGE_RRF_K` | `60` | RRF constant — 1/(k + rank) |
| `KNOWLEDGE_DEFAULT_LANGUAGE` | `fr` | Default language filter (corpus is French) |
| `KNOWLEDGE_SPARSE_MODEL` | `Qdrant/bm25` | Sparse BM25 model (tiny, bundled) |
| `KNOWLEDGE_QUERY_CACHE` | `256` | LRU cache size for E5 query embeddings |
| `KNOWLEDGE_RERANKER_ENABLED` | `false` | Cross-encoder retired from realtime |

### 8. New Files

| File | Lines | Description |
|------|-------|-------------|
| `RAG_PHASE8_REPORT.md` | 337 | Full technical report with latency, memory, calibration |
| `scripts/calibration_test.py` | 77 | 18-query French calibration suite |
| `scripts/recreate_collection_fr.py` | 98 | Drop + recreate collection with named vectors |
| `deploy/backup/honest_answers.md` | 200 | Backup of deleted root file |
| `deploy/backup/problems.md` | 500 | Backup of deleted root file |

### Files Changed

| File | Status | Lines |
|------|--------|-------|
| `.env.example` | Modified | +53/-72 |
| `honest_answers.md` | Deleted | -200 |
| `scripts/knowledge_score_probe.py` | Modified | ~121 |
| `services/knowledge-service/Dockerfile` | Modified | +2/-3 |
| `services/knowledge-service/src/knowledge_service/corpus.py` | Rewritten FR | ~61 |
| `services/knowledge-service/src/knowledge_service/embeddings.py` | Modified | +82/-2 |
| `services/knowledge-service/src/knowledge_service/ingestion.py` | Modified | +20/-6 |
| `services/knowledge-service/src/knowledge_service/main.py` | Modified | +14/-11 |
| `services/knowledge-service/src/knowledge_service/qdrant_store.py` | Modified | +28/-11 |
| `services/knowledge-service/src/knowledge_service/reranker.py` | Modified | +3/-2 |
| `services/knowledge-service/src/knowledge_service/retriever.py` | Modified | +91/-20 |
| `services/knowledge-service/src/knowledge_service/sync_worker.py` | Modified | +10/-4 |
| `RAG_PHASE8_REPORT.md` | **New** | 337 |
| `scripts/calibration_test.py` | **New** | 77 |
| `scripts/recreate_collection_fr.py` | **New** | 98 |
| `deploy/backup/honest_answers.md` | **New** | 200 |
| `deploy/backup/problems.md` | **New** | 500 |
| **Total** | | **~1,620 added, 198 deleted** |

## Database / Qdrant

**Migration required** (one-time):
```bash
# Drop old collection + recreate with named vectors (dense + bm25)
python scripts/recreate_collection_fr.py

# Re-embed all chunks from Postgres into the new index
knowledge-sync-outbox
```

## Testing Notes

- **Latency**: warm `/search` should return in ~80ms (vs 2-5s for Phase 7).
- **Control query**: "how do I fix my washing machine" must return `[]`.
- **French queries**: all 18 queries in `scripts/calibration_test.py` should
  return correct passages with appropriate rankings.
- **English query**: "how do I activate roaming" should also return `[]` (the
  English `DEFAULT_LANGUAGE=fr` filter drops cross-lingual hits).
- **Hybrid off**: set `KNOWLEDGE_HYBRID_ENABLED=false` and verify dense-only
  results (no RRF fusion).
- **Re-ingest**: after running `recreate_collection_fr.py`, verify all chunks
  are re-embedded with both dense + sparse vectors.
