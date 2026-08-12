# Phase 5b — Metadata filters + reindex recovery path

## What changed

| File | Change | Role |
|------|--------|------|
| `reindex.py` | **New** | Rebuild Qdrant from Postgres: re-embeds every live chunk from `text_content`, upserts into Qdrant. Supports `--recreate` for model migration. |
| `retriever.py` | Extended | `_build_filter()` pre-filters by `language`, `document_type`, `region` (MatchValue) and `applicable_plans`, `product_codes` (MatchAny). `search()` accepts `filters` + `min_score`. `LexicalRetriever.search` kept signature-compatible. |
| `qdrant_store.py` | Extended | 3 new payload indexes: `applicable_plans`, `product_codes`, `region` (all keyword). Qdrant narrows candidates BEFORE vector scoring. |
| `schemas.py` | Extended | `SearchRequest` now has `language`, `document_type`, `region`, `applicable_plans`, `product_codes`, `min_score` fields + `.filters()` helper. |
| `main.py` | Wired | `/search` passes `req.filters()` and `req.min_score` to the retriever. |
| `pyproject.toml` | Extended | `knowledge-reindex` console script. |

## The gap this phase closes

Before Phase 5b, Qdrant had lost the original 5 vectors (5 + 12 uploaded = 17 expected, but only 12 present). Neither `knowledge-ingest` (returns UNCHANGED because checksums match) nor `knowledge-sync-outbox` (skips succeeded events) could restore them. Postgres held `text_content` but nothing read it back into the index.

**`knowledge-reindex` solves this** — it reads every active chunk from Postgres, re-embeds from `text_content` (deterministic, local, free), and upserts into Qdrant.

## Results

### 1. Reindex — repair the lost vectors

```
DOCUMENTS=6 INDEXED=17 SKIPPED=0 POINTS_IN_COLLECTION=17
KNOWLEDGE_REINDEX_OK
```

### 2. SQL verification — chunk count must match points

```sql
SELECT count(*) FROM knowledge.chunks c
  JOIN knowledge.documents d ON d.id = c.document_id
 WHERE c.active AND d.status = 'ready';
```

```
 count
-------
    17
```

17 chunks in Postgres = 17 points in Qdrant. The index is fully repaired.

### 3. Health check

```json
{
    "status": "ok",
    "model": "intfloat/multilingual-e5-small",
    "dimensions": 384,
    "collection": "telecom_knowledge",
    "points": 17,
    "checks": {
        "embedder": "ok",
        "qdrant_collection": "ok",
        "retriever": "ok"
    }
}
```

### 4. Qdrant points_count + payload indexes

```
"points_count": 17
```

All 7 payload indexes now exist in the collection schema:
- `language` (keyword), `document_type` (keyword), `source` (keyword), `active` (bool) — from Phase 2
- `applicable_plans` (keyword), `product_codes` (keyword), `region` (keyword) — new in Phase 5b

### 5. Unfiltered search (top_k=3)

| Rank | Source | Score | Document type |
|------|--------|-------|---------------|
| 1 | `procedures/roaming-activation.md` | 0.8918 | procedures |
| 2 | `tests/env_config.txt` | 0.8185 | tests |
| 3 | `tests/env_config.txt` | 0.8098 | tests |

### 6. Filtered search (document_type=procedures, top_k=3)

| Rank | Source | Score | Document type |
|------|--------|-------|---------------|
| 1 | `procedures/roaming-activation.md` | 0.8918 | procedures |
| 2 | `procedures/plan-change.md` | 0.7713 | procedures |

The `tests/env_config.txt` chunks are correctly excluded by the pre-filter. Only `procedures/` documents returned.

## Summary

- **Recovery path exists** — `knowledge-reindex` rebuilds Qdrant from Postgres. Wiped, corrupted, or partially-lost collections are now fully recoverable. Also serves as the model-migration path: change `EMBEDDING_MODEL`, run `--recreate`, done.
- **Pre-filtering works** — Qdrant narrows candidates by `language`, `document_type`, `region`, `applicable_plans`, `product_codes` BEFORE vector scoring. `active=True` is always enforced.
- **17/17 vectors recovered** — the 5 lost original vectors plus the 12 uploaded ones are all back in the index, matching Postgres exactly.
- **Dimension safety** — reindex skips chunks embedded by a different model rather than poisoning the collection's vector space.

https://github.com/chouaib-saad/livekit_agent/tree/version_37