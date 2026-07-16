# Version 37 — RAG Phases 3–5: Ingestion Pipeline, Dense Retrieval, Upload API, Reindex

## Summary

Completes the RAG knowledge pipeline across three phases: a full ingestion
pipeline from MinIO to Postgres + Qdrant (phase 3), dense-only retrieval that
refuses to silently fall back to term-overlap (phase 4), and pre-filtered search
with an upload API and rebuild path (phase 5).

## Changes

### RAG Phase 3 — Knowledge Ingestion

**`services/knowledge-service/src/knowledge_service/ingestion.py`** (548 lines, new):
- Full pipeline: MinIO → parse → chunk → embed → Postgres + Qdrant.
- **Checksum-based idempotency**: re-ingesting unchanged bytes is a no-op, so
  nightly sweeps cost nothing.
- **Versioned**: changed bytes create version N+1 and deactivate the previous
  version's chunks; retrieval never mixes two revisions.
- Every chunk write enqueues a `KnowledgeSyncOutbox` row — a Qdrant outage
  degrades to "the index is stale" (replayable) rather than silent disagreement.
- `parse_document()` extracts metadata via YAML-like front matter (language,
  title, document_type, applicable_plans, product_codes, region).
- `chunk_text()` splits on paragraph boundaries with configurable overlap,
  preserving procedure step integrity.
- `estimate_tokens()` — conservative token count for observability.
- Console script: `knowledge-ingest`.

**`services/knowledge-service/src/knowledge_service/minio_store.py`** (107 lines, new):
- `KnowledgeStore` — list/get/put over `KNOWLEDGE_MINIO_BUCKET` (separate from
  the call-recordings bucket).
- **Loud failure**: when MinIO is unreachable, raises `KnowledgeStoreError`
  rather than silently ingesting nothing.
- Auto-creates the bucket on first use.
- `list_keys()` filters by `SUPPORTED_SUFFIXES` for deterministic runs.

**`services/knowledge-service/src/knowledge_service/parsers.py`** (190 lines, new):
- Format-specific extraction: PDF (`pypdf`), DOCX (`python-docx`), CSV, JSON,
  Markdown, plain text.
- Each extractor preserves **paragraph breaks as blank lines** — the chunker's
  split boundary.
- Stricter than the old approach: a scanned PDF with no text layer raises
  `ParseError` instead of indexing an empty document.
- CSV/JSON rendered as prose paragraphs, not raw data.

**`scripts/seed_knowledge_bucket.py`** (52 lines, new):
- Lifts the built-in `knowledge_service.corpus.CORPUS` into the MinIO bucket as
  front-mattered Markdown so `knowledge-ingest` has documents to index on day
  one. Idempotent.

### RAG Phase 4 — Dense-Only Retrieval

**`services/knowledge-service/src/knowledge_service/retriever.py`** (rewritten):
- **No silent fallback**: `get_retriever()` never returns `LexicalRetriever`
  unless `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true` is explicitly set. Previously
  it silently fell back to term-overlap whenever the vector path raised — which
  it always did because it required `OPENAI_API_KEY`, which this platform
  doesn't use. The agent therefore answered from term-overlap over an in-memory
  corpus while appearing to be RAG-backed.
- `QdrantE5Retriever` — embeds queries with the local model, searches Qdrant
  with `active=true` filter, returns full passage metadata.
- `RetrieverUnavailable` exception surfaced as 503 on `/search` — a plausible
  wrong answer is worse than a clear failure.
- `Passage` dataclass now carries `title`, `language`, `document_type`,
  `version`, and `metadata` for full source attribution.

**`services/knowledge-service/src/knowledge_service/sync_worker.py`** (150 lines, new):
- Postgres → Qdrant outbox drain. Separates intent (Postgres rows) from index
  (Qdrant points).
- Exponential backoff, max 8 attempts, cap at 600 s.
- `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent safety.
- Upserts re-embed the chunk text (deterministic, local, no quota).
- Console script: `knowledge-sync-outbox`.

### RAG Phase 5 — Pre-Filtered Search + Upload API

**`services/knowledge-service/src/knowledge_service/schemas.py`** (extended):
- `SearchRequest` adds optional filters: `language`, `document_type`, `region`,
  `applicable_plans`, `product_codes`, `min_score`.
- `PassageModel` now carries `title`, `language`, `document_type`, `version`,
  `metadata`.
- New `UploadResponse` model.

**`services/knowledge-service/src/knowledge_service/main.py`** — upload endpoint:
- `POST /knowledge/upload` — accepts PDF/DOCX/CSV/JSON/MD/TXT, stores in MinIO,
  auto-ingests, drains outbox, returns document metadata.
- Runs ingestion in a thread pool to avoid blocking `/search`.

**`services/knowledge-service/src/knowledge_service/qdrant_store.py`**:
- New payload indexes: `applicable_plans` (keyword), `product_codes` (keyword),
  `region` (keyword).

**`services/knowledge-service/src/knowledge_service/retriever.py`** — pre-filter:
- `_build_filter()` translates caller filters into a Qdrant pre-filter.
  List-valued payloads use `MatchAny`. `active=true` always enforced.

**`services/knowledge-service/src/knowledge_service/reindex.py`** (111 lines, new):
- Rebuild Qdrant from Postgres text. Deterministic, local, free.
- `--recreate` drops the collection first (for model migration).
- Skips chunks whose `embedding_dimensions` don't match the configured model.
- Console script: `knowledge-reindex`.

### Containers & Dependencies

- **Dockerfile**: copies `/app/scripts/` into image (for `seed_knowledge_bucket`)
- **docker-compose.apps.yml**: adds `MINIO_ENDPOINT`, `MINIO_ROOT_USER`,
  `MINIO_ROOT_PASSWORD`, `MINIO_SECURE`, `KNOWLEDGE_MINIO_BUCKET` env vars;
  adds `depends_on: minio`
- **pyproject.toml**: adds `persistence`, `object-storage`, `minio>=7.2`,
  `pypdf==5.9.0`, `python-docx==1.2.0`, `python-multipart==0.0.32`
- **New console scripts**: `knowledge-ingest`, `knowledge-sync-outbox`,
  `knowledge-reindex`
- **`.env.example`**: adds `KNOWLEDGE_MINIO_BUCKET`, `KNOWLEDGE_CHUNK_MAX_CHARS`,
  `KNOWLEDGE_CHUNK_OVERLAP_CHARS`, `KNOWLEDGE_EMBED_BATCH`,
  `KNOWLEDGE_MAX_UPLOAD_MB`
- **No LiveKit SDK version changes.**

### Files Changed

| File | Status | Lines |
|------|--------|-------|
| `.env.example` | Modified | +9/-0 |
| `infra/docker-compose/docker-compose.apps.yml` | Modified | +8/-0 |
| `services/knowledge-service/Dockerfile` | Modified | +1/-0 |
| `services/knowledge-service/pyproject.toml` | Modified | +9/-0 |
| `services/knowledge-service/src/knowledge_service/main.py` | Modified | +43/-6 |
| `services/knowledge-service/src/knowledge_service/qdrant_store.py` | Modified | +5/-0 |
| `services/knowledge-service/src/knowledge_service/retriever.py` | Rewritten | ~180 |
| `services/knowledge-service/src/knowledge_service/schemas.py` | Modified | +44/-5 |
| `services/knowledge-service/src/knowledge_service/sync_worker.py` | **New** | 150 |
| `services/knowledge-service/src/knowledge_service/ingestion.py` | **New** | 548 |
| `services/knowledge-service/src/knowledge_service/minio_store.py` | **New** | 107 |
| `services/knowledge-service/src/knowledge_service/parsers.py` | **New** | 190 |
| `services/knowledge-service/src/knowledge_service/reindex.py` | **New** | 111 |
| `scripts/seed_knowledge_bucket.py` | **New** | 52 |
| `results.md` | Modified | +1/-1 |
| **Total** | | **~1,482 added, 61 deleted** |

## Database / Qdrant

- **New DB tables**: `knowledge_documents`, `knowledge_chunks`,
  `knowledge_ingestion_jobs`, `knowledge_sync_outbox` (via `packages/persistence`)
- **Seed the knowledge bucket** (one-time):
  ```bash
  python /app/scripts/seed_knowledge_bucket.py
  ```
- **Ingest documents**:
  ```bash
  knowledge-ingest
  ```
- **Drain the outbox** (after ingestion):
  ```bash
  knowledge-sync-outbox
  ```
- **Rebuild the index** (after model change or Qdrant wipe):
  ```bash
  knowledge-reindex --recreate
  ```

## Testing Notes

- **Ingestion**: run `knowledge-ingest` with documents in the knowledge bucket.
  Verify checksum-based idempotency (re-run shows UNCHANGED).
- **Versioning**: upload a new version of a document; verify old chunks
  deactivated and new ones indexed.
- **Search**: send a query with `language`, `document_type`, or
  `applicable_plans` filters; verify pre-filter narrows candidates before vector
  scoring.
- **Upload API**: POST a PDF/DOCX to `/knowledge/upload`; verify it appears in
  search results immediately (outbox drained).
- **Reindex**: re-run `knowledge-reindex --recreate` after an embedding model
  change; verify all chunks re-embedded.
- **503 path**: take Qdrant down; verify `/search` returns 503, not fallback
  results.
