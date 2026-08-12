# Phase 4 — Dense retrieval + outbox drain

## What changed

| File | Change | Role |
|------|--------|------|
| `src/knowledge_service/retriever.py` | Rewritten | `QdrantE5Retriever` — no silent lexical fallback; `build_retriever()` raises on empty collection or missing Qdrant |
| `src/knowledge_service/sync_worker.py` | **New** | Outbox drain: replays `knowledge.sync_outbox` upserts into Qdrant re-embedding from `text_content` |
| `src/knowledge_service/schemas.py` | Enriched | `PassageModel` now carries `title`, `language`, `document_type`, `version`, `metadata` |
| `src/knowledge_service/main.py` | Rewired | Lazy retriever; `/search` returns 503 on failure instead of serving lexical results |
| `pyproject.toml` | +1 line | `knowledge-sync-outbox` script entry |

## Pipeline results

### 1. Qdrant collection bootstrap

```
collection=telecom_knowledge  dimensions=384  distance=cosine  points=0
QDRANT_BOOTSTRAP_OK
```

### 2. Outbox drain (5 stranded upserts → Qdrant)

```
UPSERTED=5 DELETED=0 ORPHAN=0 INACTIVE=0 FAILED=0
KNOWLEDGE_SYNC_OK
```

Each upsert re-embedded the chunk from `knowledge.chunks.text_content` (deterministic, local, no quota).

### 3. Qdrant points_count

```
"points_count": 5
```

### 4. Health check

```json
{
    "status": "ok",
    "model": "intfloat/multilingual-e5-small",
    "dimensions": 384,
    "collection": "telecom_knowledge",
    "points": 5,
    "checks": {
        "embedder": "ok",
        "qdrant_collection": "ok",
        "retriever": "ok"
    }
}
```

All three checks pass — the service would serve requests.

### 5. Postgres outbox audit

```
 status   | count
----------+-------
 succeeded |     5
```

0 pending — every event drained.

### 6. Cross-lingual dense retrieval (the verdict)

| Query | Result 1 | Score |
|-------|----------|-------|
| `how do I activate roaming abroad` | `procedures/roaming-activation.md` v1 [en/procedures] | 0.895 |
| `comment activer le roaming a l etranger` | `procedures/roaming-activation.md` v1 [en/procedures] | 0.861 |
| `كيف أفعل التجوال الدولي` | `procedures/roaming-activation.md` v1 [en/procedures] | 0.831 |

All three languages surface the correct procedure as top result. The aligned E5 multilingual vector space works across English, French, and Arabic queries against an English corpus.

## Summary

- **Silent downgrade eliminated** — `get_retriever()` now raises `RetrieverUnavailable` instead of returning a term-overlap fallback. `LexicalRetriever` is still importable for offline tests; production reach requires `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true`.
- **5/5 outbox events drained** — all stranded upserts reached Qdrant in one pass.
- **Dense retrieval confirmed** — cross-lingual queries return the correct English procedure, proving the E5 vector space is correctly aligned.
- **503 on failure** — empty collection, missing Qdrant, or broken embedder all produce a clear 503 instead of plausible-sounding fiction.




| Red Flag | Was it real? | Fixed? | Current status |
|---|---|---|---|
| **RF1** — Qdrant collection didn't exist | ✅ Real. `knowledge-ingest` ran before `knowledge-bootstrap-qdrant`, so every upsert got a 404. | ✅ `knowledge-bootstrap-qdrant` exists and creates `telecom_knowledge` (384d, cosine, HNSW, payload indexes on `language`, `document_type`, `source`, `active`). | **RESOLVED** — Run once after deploy. |
| **RF2** — Idempotency prevented re-indexing after collection was created | ✅ Real. Checksums matched on second run → `INGESTED=0 UNCHANGED=5`. Vectors could never reach Qdrant without the outbox. | ✅ `sync_worker.py` + `knowledge-sync-outbox` script created. Drains `knowledge.sync_outbox` with re-embedding, dimension validation, exponential backoff (max 8 attempts). | **RESOLVED** — Run after every ingestion. |
| **RF3** — Silent lexical fallback | ✅ Real. `get_retriever()` swallowed `KeyError` on missing `OPENAI_API_KEY` and returned `LexicalRetriever` without warning. Agent answered from term-overlap while appearing RAG-backed. | ✅ `retriever.py` rewritten. `build_retriever()` raises `RetrieverUnavailable` on any failure. `/search` returns HTTP 503. `LexicalRetriever` reachable only via explicit `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true`. | **RESOLVED** — No silent degradation possible. |

---

## What currently works (truth)

| Capability | Status | Details |
|---|---|---|
| **MinIO knowledge bucket** | ✅ Working | Bucket `telecom-knowledge` created on first use. 5 documents seeded. |
| **Parsing** (MD + front matter) | ✅ Working | Regex-based front matter parsing, language detection (FR/AR/EN/und), title inference, document type from path. |
| **Chunking** | ✅ Working | Paragraph-first, 1200 char budget, 150 char overlap, hard-split oversized paragraphs. |
| **Embedding** | ✅ Working | `intfloat/multilingual-e5-small` ONNX model, 384 dims, CPU, baked into Docker image at build time. `query:` / `passage:` prefix applied correctly. |
| **Postgres persistence** | ✅ Working | `knowledge.documents`, `knowledge.chunks`, `knowledge.ingestion_jobs`, `knowledge.sync_outbox` all writing correctly. |
| **Qdrant collection** | ✅ Working | Collection exists, payload indexes created, HNSW configured. |
| **Outbox drain** | ✅ Working | `knowledge-sync-outbox` drains pending events with re-embedding, dimension validation, concurrency safety (`FOR UPDATE SKIP LOCKED`). |
| **Health endpoint** | ✅ Working | Three checks (embedder, qdrant_collection, retriever). Returns `"ok"` or `"degraded"` + 503. |
| **Dense retrieval** | ✅ Working | `QdrantE5Retriever` searches only `active=True` chunks. Cross-lingual verified (EN/FR/AR queries return correct English document). |
| **Auth** | ✅ Working | `/search` protected by `require_internal_key` from `service-auth`. |
| **Idempotency** | ✅ Working | SHA-256 checksums prevent re-embedding unchanged documents. |

---



{
    "status": "degraded",
    "model": "intfloat/multilingual-e5-small",
    "dimensions": 384,
    "collection": "telecom_knowledge",
    "points": 0,
    "checks": {
        "embedder": "ok",
        "qdrant_collection": "ok",
        "retriever": "error: collection 'telecom_knowledge' is empty: ingest the corpus (`knowledge-ingest`) and drain the outbox (`knowledge-sync-outbox`)"
    }
}

