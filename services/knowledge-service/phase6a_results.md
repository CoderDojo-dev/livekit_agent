# Phase 6a — Corpus lifecycle (list + purge)

## What changed

| File | Change | Role |
|------|--------|------|
| `lifecycle.py` | **New** | `list_documents()` — corpus inventory with live chunk counts. `purge_document()` — full removal across Postgres → Outbox → Qdrant → MinIO. |
| `minio_store.py` | Extended | `delete()` method on `KnowledgeStore` — removes object from the bucket. |
| `schemas.py` | Extended | `DocumentSummary`, `DocumentListResponse`, `PurgeResponse` models. |
| `main.py` | Extended | `GET /knowledge/documents` — corpus inventory. `DELETE /knowledge/documents/{source:path}` — purge. |

## The problem this solves

Before Phase 6a, the corpus had 3 endpoints: `/health`, `/search`, `/knowledge/upload`. No list, no delete. A test artifact (`tests/env_config.txt`) was 12 of 17 chunks — 70% of the corpus — and scored 0.8185 on "how do I activate roaming", taking rank #2. It could not be removed.

## Results

### 1. List documents — see what the agent answers from

```
GET /knowledge/documents
```

```
total_documents: 6
total_chunks: 17

  source                          status   chunks  document_type
  faq/billing-cycle.md            ready    1       faq
  faq/data-troubleshooting.md    ready    1       faq
  offers/forfait-flexi.md         ready    1       offers
  procedures/plan-change.md       ready    1       procedures
  procedures/roaming-activation.md ready    1       procedures
  tests/env_config.txt            ready    12      tests    ← 70% of corpus, junk
```

### 2. Purge the test artifact

```
DELETE /knowledge/documents/tests/env_config.txt
```

```json
{
    "source": "tests/env_config.txt",
    "documents_archived": 1,
    "chunks_deactivated": 12,
    "points_removed": 12,
    "object_removed": true
}
```

### 3. Qdrant after purge

```
"points_count": 5
```

17 → 5. The 12 junk chunks are gone from the index.

### 4. Health after purge

```json
{
    "status": "ok",
    "points": 5,
    "checks": {
        "embedder": "ok",
        "qdrant_collection": "ok",
        "retriever": "ok"
    }
}
```

### 5. Search after purge — noise is gone

| Rank | Source | Score | Document type |
|------|--------|-------|---------------|
| 1 | `procedures/roaming-activation.md` | 0.8918 | procedures |
| 2 | `faq/data-troubleshooting.md` | 0.7953 | faq |
| 3 | `offers/forfait-flexi.md` | 0.7785 | offers |

Ranks #2 and #3 are now **real telecom documents**. Before the purge they were `tests/env_config.txt` at 0.8185 and 0.8098.

## Purge order (deliberate — nothing stranded)

1. **Postgres** — chunks deactivated (`active=false`), document archived (`status=archived`)
2. **Outbox** — delete events queued (a Qdrant outage still converges)
3. **Qdrant** — points dropped immediately (best-effort)
4. **MinIO** — object removed (or the next `knowledge-ingest` re-ingests it as a new version)

Step 4 is critical: an archived document no longer matches the `status='ready'` checksum guard, so leaving the file in the bucket means the next scan silently resurrects it.

## Summary

- **Corpus is now curatable** — operators can list what's indexed and remove mistakes.
- **Purge is a full removal** — Postgres (soft: archived, audit trail survives), Qdrant (hard: points deleted), MinIO (hard: object removed). `knowledge-reindex` correctly ignores archived documents.
- **Search quality restored** — the env config noise that polluted 70% of the corpus and outranked real procedures is gone. The agent now answers from 5 real telecom documents.
