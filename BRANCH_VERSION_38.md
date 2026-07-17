# Version 38 — Relevance Gate + MCP Resilience + Corpus Lifecycle (RAG Phase 6)

## Summary

RAG phase 6 adds three capabilities that close the loop on a production RAG
pipeline: a **relevance gate** that makes the agent say "I don't know" instead of
inventing from filler, **MCP tool resilience** so a knowledge-service outage
never takes down a call, and a **corpus lifecycle API** so operators can see
what is indexed and remove mistaken uploads.

## Changes

### 1. Relevance Gate (`services/knowledge-service/src/knowledge_service/retriever.py`)

E5's low-temperature InfoNCE training compresses cosine scores into ~0.7–1.0,
even for documents with nothing to do with the query. Without a gate the agent
grounds answers on filler when the knowledge base has no real answer.

**Two-stage filter** — a passage survives only if it clears BOTH:
- **FLOOR** (0.80): absolute cutoff. Kills the "nothing is relevant" case.
- **RELATIVE** (0.97): share of the top score. Kills "one good hit + filler".

`apply_relevance_gate()` returns an empty list when nothing passes — a valid,
desirable answer that makes the agent say "I do not have that information."

**Language asymmetry** (structural, not a tuning artifact): cross-lingual
headroom above the 0.7880 noise ceiling is en=0.107, fr=0.073, ar=0.043. One
global FLOOR is ~2.5x tighter for Arabic. Watch for Arabic false negatives first.

### 2. MCP Tool Resilience (`mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py`)

- **Before**: `raise_for_status()` on a 503 raised inside the tool call; the LLM
  blocked, the agent produced no speech, and the caller heard silence.
- **After**: on 503 or network error, logs the failure and returns `[]`. The
  agent says it has no information and the conversation continues.
- Configurable timeout via `KNOWLEDGE_SEARCH_TIMEOUT_S` (default 5.0 s).

### 3. Corpus Lifecycle API (`services/knowledge-service/src/knowledge_service/`)

**`lifecycle.py`** (122 lines, new):
- `list_documents(session)` — returns every document with source, title,
  language, document_type, version, status, live chunk count, checksum.
- `purge_document(session, source, remove_object)` — full removal across all
  three stores in order that cannot strand data:
  1. Postgres — deactivate chunks, archive documents
  2. Outbox — queue the deletes (so a Qdrant outage still converges)
  3. Qdrant — drop the points now (best-effort; outbox is fallback)
  4. MinIO — remove the object (or the next bucket scan re-ingests it)

**`minio_store.py`** — added `delete()` method (idempotent).

**`main.py`** — two new endpoints:
- `GET /knowledge/documents` — corpus inventory
- `DELETE /knowledge/documents/{source}` — purge (with `remove_object` param)

**`schemas.py`** — new models: `DocumentSummary`, `DocumentListResponse`,
`PurgeResponse`.

### 4. Calibration Script (`scripts/knowledge_score_probe.py`, new)

Prints the TRUE ungated ranking from Qdrant (`apply_gate=False`) — essential
for calibrating the relevance gate thresholds. Reports noise ceiling, FLOOR
margin, and per-language headroom for each test query.

### 5. Configuration (`.env.example`)

- `KNOWLEDGE_SCORE_FLOOR=0.80`
- `KNOWLEDGE_RELATIVE_CUTOFF=0.97`
- `KNOWLEDGE_SEARCH_TIMEOUT_S=5.0`

### Files Changed

| File | Status | Lines |
|------|--------|-------|
| `.env.example` | Modified | +15/-0 |
| `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py` | Modified | +27/-8 |
| `services/knowledge-service/src/knowledge_service/main.py` | Modified | +53/-1 |
| `services/knowledge-service/src/knowledge_service/minio_store.py` | Modified | +8/-0 |
| `services/knowledge-service/src/knowledge_service/retriever.py` | Modified | +81/-1 |
| `services/knowledge-service/src/knowledge_service/schemas.py` | Modified | +32/-0 |
| `services/knowledge-service/src/knowledge_service/lifecycle.py` | **New** | 122 |
| `scripts/knowledge_score_probe.py` | **New** | 85 |
| **Total** | | **~425 added, 8 deleted** |

## Containers & Dependencies

- **No container image changes** in this version.
- **No new dependencies** in this version.
- The new `DELETE` endpoint references `lifecycle.purge_document` which is
  already imported via the existing knowledge-service module tree.

## Testing Notes

- **Relevance gate**: call `/search` with an irrelevant query (e.g. "fix my
  washing machine") and verify it returns an empty passages list instead of
  filler documents.
- **MCP resilience**: stop the knowledge-service and call the agent's
  `knowledge_search` tool; verify it returns `[]` and the agent continues
  speaking.
- **List documents**: call `GET /knowledge/documents` and verify the document
  inventory matches the ingested corpus.
- **Purge**: upload a document, call `DELETE /knowledge/documents/{source}`,
  then verify the document is absent from `/search` results and the MinIO
  bucket.
- **Calibration**: run `knowledge_score_probe.py` inside the container and
  verify the noise ceiling / per-language headroom report.
