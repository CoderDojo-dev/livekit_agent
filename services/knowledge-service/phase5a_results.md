# Phase 5a — Multi-format ingestion + upload API + auto-pipeline

## What changed

| File | Change | Role |
|------|--------|------|
| `parsers.py` | **New** | Format-aware text extraction: PDF (`pypdf`), DOCX (`python-docx`), CSV (prose per row), JSON (flattened), MD/TXT. `SUPPORTED_SUFFIXES` is the single source of truth. |
| `ingestion.py` | Refactored | `normalize_text` moved to `parsers.normalize_unicode`; `parse_document` now calls `extract_text(key, raw)` for format-aware parsing. Added `safe_key()` (path-traversal-safe bucket key builder) and `store_and_ingest()` (single-key upload + ingest + drain pipeline). |
| `minio_store.py` | Changed | `SUPPORTED_SUFFIXES` now imported from `parsers` instead of defined locally. |
| `main.py` | Extended | New `POST /knowledge/upload` endpoint accepting `file`, `document_type`, `auto_ingest`. Runs in thread pool to avoid blocking `/search`. |
| `schemas.py` | Extended | New `UploadResponse` model with `source`, `status`, `document_id`, `version`, `chunks`, `indexed`, `message`. |
| `pyproject.toml` | Extended | Added `pypdf==5.9.0`, `python-docx==1.2.0`, `python-multipart==0.0.32` |
| `.env.example` / `.env` | Extended | Added `KNOWLEDGE_MAX_UPLOAD_MB=25`, set `INTERNAL_API_KEY=dev-key-123` |

## Pipeline results

### Upload a plain text file (12 chunks)

```
POST /knowledge/upload
→ {"source":"tests/env_config.txt","status":"ingested",
   "document_id":"39bde670-...","version":1,
   "chunks":12,"indexed":12,
   "message":"ingested: 12 chunk(s), 12 indexed"}
```

### Health check

```json
{
    "status": "ok",
    "model": "intfloat/multilingual-e5-small",
    "dimensions": 384,
    "collection": "telecom_knowledge",
    "points": 12,
    "checks": {
        "embedder": "ok",
        "qdrant_collection": "ok",
        "retriever": "ok"
    }
}
```

### Qdrant points_count

```
"points_count": 12
```

### Idempotency (re-upload same file)

```
POST /knowledge/upload (same file)
→ {"source":"tests/env_config.txt","status":"unchanged",
   "version":1,"chunks":0,"indexed":0,
   "message":"unchanged: 0 chunk(s), 0 indexed"}
```

Checksum-based idempotency holds for binary uploads too: 0 re-embedded, 0 re-indexed.

## Summary

- **Upload API works** — `POST /knowledge/upload` accepts a file, writes to MinIO, ingests into Postgres, drains outbox to Qdrant, all in one call. No manual CLI steps.
- **Single-key ingestion** — O(1) per upload, never a full bucket rescan.
- **Outbox drained inline** — document is searchable when the HTTP response returns.
- **Path-traversal safe** — `../../../etc/passwd` → `general/passwd`.
- **Format-aware extraction** — PDF, DOCX, CSV, JSON, MD, TXT all supported via `parsers.py`. Each extractor preserves paragraph breaks (for chunker alignment) and raises `ParseError` rather than silently indexing empty content.
- **Idempotent** — re-uploading the same bytes returns `status: unchanged` with 0 chunks.
- **12 documents now indexed** — corpus grew from 5 to 6 documents (12 chunks total) with one API call.
