# Problems & resolution steps

This document captures problems encountered during Phase 3–4 of the RAG pipeline, the root causes, and the exact steps to resolve each one.

---

## RED FLAG 1 — Qdrant has zero vectors

**Symptom:** During Phase 3 ingestion, Qdrant returned 404 for every upsert: `Collection telecom_knowledge doesn't exist!`. The ingestion pipeline logged `qdrant sync failed (outbox will replay)` and continued.

**Root cause:** The `knowledge-bootstrap-qdrant` step (which creates the Qdrant collection with the correct dimension and distance) was never run. The collection `telecom_knowledge` simply did not exist. This is not "deferred to Phase 6" — it's the index being empty, so all upserts were silently lost.

**Resolution:**
```bash
# 1. Create the collection with matching dimension (384) and distance (cosine)
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml \
  run --rm knowledge-service knowledge-bootstrap-qdrant

# 2. Verify the collection exists and has 0 points (expected before drain)
curl -s localhost:6333/collections/telecom_knowledge | python3 -m json.tool | grep points_count
# Expected: "points_count": 0
```

---

## RED FLAG 2 — Outbox trap: re-running `knowledge-ingest` never retries Qdrant

**Symptom:** After the collection was created, re-running `knowledge-ingest` returned `INGESTED=0 UNCHANGED=5`. The vectors never reached Qdrant.

**Root cause:** The checksum-based idempotency correctly recognized that the source bytes in MinIO had not changed — so the documents were returned with `status=unchanged`. The ingestion pipeline never re-embedded, never re-upserted to Qdrant, and never re-created the outbox events. The outbox (scheduled for Phase 6) was the only surviving path for those vectors to reach the index, but there was no worker to drain it.

**Resolution — outbox drain worker (`knowledge-sync-outbox`):**

```bash
# Drain all pending outbox events into Qdrant (re-embeds from text_content)
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml \
  run --rm knowledge-service knowledge-sync-outbox

# Expected output:
#   UPSERTED=5 DELETED=0 ORPHAN=0 INACTIVE=0 FAILED=0
#   KNOWLEDGE_SYNC_OK
```

The worker:
- Fetches pending/failed events ordered by `available_at` (with `FOR UPDATE SKIP LOCKED` for concurrency safety)
- Re-embeds each chunk from `knowledge.chunks.text_content` (not from Postgres vectors — they aren't stored)
- Validates that the current embedder emits the same dimension as stored on the chunk (prevents mixing incompatible vector spaces)
- Pushes to Qdrant using the same `qdrant_payload()` function used during ingestion
- Handles dimension mismatch, orphan chunks, and inactive chunks without crashing

**Post-drain verification:**
```bash
# Qdrant should now have vectors
curl -s localhost:6333/collections/telecom_knowledge | python3 -m json.tool | grep points_count
# Expected: "points_count": 5

# Outbox should be all succeeded
docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres psql -U telecom -d telecom \
  -c "SELECT status, count(*) FROM knowledge.sync_outbox GROUP BY 1;"
# Expected:
#  status   | count
# ----------+-------
#  succeeded |     5
```

---

## RED FLAG 3 — Silent lexical downgrade (Phase 4 fix)

**Symptom:** The original `get_retriever()` factory called `_openai_embedder()`, which required `OPENAI_API_KEY`. Since the platform does not use OpenAI, this raised `KeyError`, which was caught, and `LexicalRetriever` was returned silently. The agent answered from term-overlap over an in-memory corpus while appearing to be RAG-backed.

**Root cause:** A try/except swallowed the vector path failure and fell back to an offline lexical retriever with no warning.

**Resolution:** The retriever factory was rewritten to:
- Raise `RetrieverUnavailable` when the collection or embedder is unusable
- Never return `LexicalRetriever` unless `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true` is explicitly set
- Return 503 on `/search` and `/health` when the retriever is unavailable

```bash
# Verify the fix — /health must show retriever: ok
curl -s localhost:8102/health | python3 -m json.tool

# Expected:
# {
#     "checks": {
#         "embedder": "ok",
#         "qdrant_collection": "ok",
#         "retriever": "ok"
#     }
# }
```

---

## EDGE CASE — Chunk ORM has no relationship to Document

**Symptom:** The first draft of `sync_worker.py` accessed `chunk.document.title`, which would throw `AttributeError` on every outbox event.

**Root cause:** The `KnowledgeChunk` and `KnowledgeDocument` ORM models declare no SQLAlchemy relationships. Accessing `chunk.document` is not a valid path.

**Fix:** Load the parent document explicitly by primary key:
```python
document = session.get(KnowledgeDocument, chunk.document_id)
```
This is now the pattern used in `_apply_upsert()`.

---

## EDGE CASE — Dimension mismatch on replay

**Symptom:** If the embedding model is changed between ingestion and outbox drain, replaying an outbox event would push vectors of a different dimension into the collection, corrupting the vector space.

**Fix:** `_apply_upsert()` checks that `len(vector) == chunk.embedding_dimensions` before pushing. If they differ, it raises `RuntimeError` with a clear message:
```
chunk <id> was embedded as 384d by 'intfloat/multilingual-e5-small';
current model emits 768d - re-ingest instead
```
The event is marked `failed` with backoff, and the operator must re-ingest the corpus.

---

## VERIFICATION — Cross-lingual retrieval test

After all fixes are applied, run the definitive cross-lingual test:

```python
from knowledge_service.retriever import get_retriever
for q in ['how do I activate roaming abroad',
          'comment activer le roaming a l etranger',
          'كيف أفعل التجوال الدولي']:
    print(q)
    for p in get_retriever().search(q, top_k=2):
        print(f'   {p.score:.3f}  {p.source}  [{p.language}/{p.document_type} v{p.version}]')
```

**Expected result:** All three languages surface `procedures/roaming-activation.md` as the top result with scores >0.8, proving the multilingual E5 aligned vector space is working.
