# Phase 3 — Knowledge ingestion pipeline (MinIO + `knowledge-ingest`)

## State of the codebase

| File | Status | Role |
|------|--------|------|
| `scripts/seed_knowledge_bucket.py` | created | lifts built-in `CORPUS` into MinIO as front-mattered Markdown |
| `services/knowledge-service/src/knowledge_service/minio_store.py` | created | `KnowledgeStore` (list/get/put) over the `telecom-knowledge` bucket |
| `services/knowledge-service/src/knowledge_service/ingestion.py` | created | parse → chunk → embed → Postgres → outbox → Qdrant |
| `services/knowledge-service/Dockerfile` | patched | `COPY scripts/ /app/scripts/` so the seed is available at runtime |
| `.env`, `.env.example` | patched | `KNOWLEDGE_MINIO_BUCKET`, `KNOWLEDGE_CHUNK_MAX_CHARS`, `KNOWLEDGE_CHUNK_OVERLAP_CHARS`, `KNOWLEDGE_EMBED_BATCH` |
| `infra/docker-compose/docker-compose.apps.yml` | patched | MinIO env vars + `minio` dependency on `knowledge-service` |
| `pyproject.toml` (knowledge-service) | patched | `persistence`, `minio>=7.2`, `object-storage`, `knowledge-ingest` script entry |

## Results

### Seed the bucket

```
BUCKET=telecom-knowledge OBJECTS_WRITTEN=5
KNOWLEDGE_SEED_OK
```

### First `knowledge-ingest`

```
INGESTED=5 UNCHANGED=0 FAILED=0 CHUNKS=5
KNOWLEDGE_INGEST_OK
```

Qdrant collection `telecom_knowledge` does not exist yet → 5 `sync_outbox` rows
enqueued (Phase 6 replay). No data lost.

### Second `knowledge-ingest` (idempotency)

```
INGESTED=0 UNCHANGED=5 FAILED=0 CHUNKS=0
KNOWLEDGE_INGEST_OK
```

All five documents recognised as unchanged by checksum — zero re-embedding.

### Postgres audit

```
              source              |             title              | language | document_type | version | status
----------------------------------+--------------------------------+----------+---------------+---------+--------
 faq/billing-cycle.md             | Invoice and billing cycle      | en       | faq           |       1 | ready
 faq/data-troubleshooting.md      | Mobile data is not working     | en       | faq           |       1 | ready
 offers/forfait-flexi.md          | Forfait Flexi postpaid plan    | en       | offers        |       1 | ready
 procedures/plan-change.md        | Change your mobile plan        | en       | procedures    |       1 | ready
 procedures/roaming-activation.md | Activate international roaming | en       | procedures    |       1 | ready

 chunk_count:    5
 job_count:     10 succeeded
 outbox_pending: 5
```

## Summary

- **5/5 documents ingested** — every `CORPUS` entry parsed, chunked, embedded (E5-384), and
  persisted in `knowledge.documents` + `knowledge.chunks`.
- **Idempotent** — second run produced 5 unchanged, 0 re-embedded.
- **Qdrant deferred** — all 5 upserts queued in `knowledge.sync_outbox` awaiting Phase 6.
- **Edge-case robustness** — `minio_store.py` creates the bucket on first use,
  `ingestion.py` wraps each object in a per-key transaction so a single bad file never aborts
  the corpus, and the outbox guarantees eventual consistency with Qdrant.
