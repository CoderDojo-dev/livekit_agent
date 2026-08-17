# RAG knowledge-service: implementation and operations cookbook

## Scope and verified result

This cookbook covers only the RAG knowledge-service work item: readiness, corpus inventory, upload and unchanged re-upload, retrieval, safe single-document purge, and post-purge verification.

Runtime verification used the existing Docker Compose stack and disposable sources under `runtime-verification/`. No pre-existing user document was purged. No secret value is recorded here or in the evidence artifacts.

| Capability | Result | Runtime evidence |
|---|---|---|
| Readiness/health | **Proven** | `GET /health` returned 200, `status=ok`; dense embedder, Qdrant collection, retriever, sparse embedder, and CE gate all reported `ok`; 384 dimensions; 296 baseline points. |
| Inventory/list | **Proven** | `GET /knowledge/documents` returned 200. Initial active corpus: 21 documents and 296 chunks. The disposable upload appeared once as `ready`. |
| Upload and repeat | **Proven** | First upload returned `ingested`, version 1, one chunk/indexed point. Byte-identical repeat returned `unchanged`, version 1, zero chunks and zero indexed points. |
| Retrieval/search | **Proven for the running corpus** | `/search` returned roaming and billing sources for representative queries. The disposable synthetic document indexed successfully but was rejected by the configured relevance/CE gates, returning no passage; this is fail-closed behavior, not proof of synthetic retrieval. |
| Purge and post-purge | **Proven** | Purge affected only the exact disposable source: one document archived, one chunk deactivated, one Qdrant point and MinIO object removed. Active chunks returned to 296 and subsequent search did not return the source. Inventory retains an archived audit row by design. |

Evidence files:

- `artifacts/rag-runtime-verification.json` — full readiness, inventory, upload/repeat, first search, purge, and post-purge results.
- `artifacts/rag-runtime-verification-retrieval.json` — second disposable test and explicit archived-row semantics.
- `artifacts/rag-runtime-existing-retrieval.json` — successful runtime retrieval against the existing corpus.

## Architecture inspected

The supported path is the two-file Compose stack:

- `infra/docker-compose/docker-compose.yml`: PostgreSQL 16, Qdrant 1.12.5, MinIO, Redis, telemetry.
- `infra/docker-compose/docker-compose.apps.yml`: `knowledge-service` on host `127.0.0.1:8102`, with container DNS endpoints for PostgreSQL, Qdrant, and MinIO and a persistent model volume.
- `services/knowledge-service/src/knowledge_service/main.py`: FastAPI endpoints and readiness behavior.
- `ingestion.py`: MinIO -> parser/chunker -> embeddings -> PostgreSQL system of record -> Qdrant derived index; checksum idempotency.
- `lifecycle.py`: inventory and exact-source purge; historical document rows are archived rather than physically deleted.
- `retriever.py`: dense/sparse retrieval, score filtering, fusion, and optional CE gate.
- `apps/agent-worker/src/mcp_clients/knowledge_toolset.py`: agent-side MCP adapter; it is not required for direct operational verification.
- `services/knowledge-service/Dockerfile`: baked dense/sparse models, runtime CE warm-up, and `/health` container probe.

The service requires PostgreSQL, Qdrant, MinIO, and model weights. PostgreSQL is authoritative; Qdrant is rebuildable; MinIO holds source objects.

## Prerequisites

- Docker Desktop with Compose v2.
- Ports available: `5432`, `6333`, `9000`, `9001`, and `127.0.0.1:8102`.
- Repository `.env` populated. Never print or commit its values.
- PowerShell and either `curl.exe` or Python/httpx for multipart upload.

Relevant environment variable **names** (values deliberately omitted):

```text
DATABASE_URL
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
INTERNAL_API_KEY
KNOWLEDGE_SERVICE_URL
QDRANT_URL
QDRANT_COLLECTION
QDRANT_TIMEOUT_S
EMBEDDING_MODEL
EMBEDDING_DIMENSIONS
EMBEDDING_CACHE_DIR
KNOWLEDGE_SCORE_FLOOR
KNOWLEDGE_RELATIVE_CUTOFF
KNOWLEDGE_HYBRID_ENABLED
KNOWLEDGE_RRF_K
KNOWLEDGE_CE_GATE_ENABLED
KNOWLEDGE_CE_MODEL
KNOWLEDGE_CE_THRESHOLD
KNOWLEDGE_RERANKER_ENABLED
KNOWLEDGE_SEARCH_TIMEOUT_S
MINIO_ENDPOINT
MINIO_ROOT_USER
MINIO_ROOT_PASSWORD
MINIO_SECURE
KNOWLEDGE_MINIO_BUCKET
KNOWLEDGE_CHUNK_MAX_CHARS
KNOWLEDGE_CHUNK_OVERLAP_CHARS
KNOWLEDGE_EMBED_BATCH
KNOWLEDGE_MAX_UPLOAD_MB
```

All non-health endpoints require `X-API-Key` when `INTERNAL_API_KEY` is configured. `/health` is intentionally unauthenticated for probes.

## Safest startup path

From the repository root:

```powershell
$F = "infra/docker-compose/docker-compose.yml"
$A = "infra/docker-compose/docker-compose.apps.yml"

docker compose -f $F -f $A up -d postgres qdrant minio
docker compose -f $F -f $A up -d --build knowledge-service
docker compose -f $F -f $A ps postgres qdrant minio knowledge-service
docker compose -f $F -f $A logs --tail=200 knowledge-service
```

If the current image is already valid, omit `--build`. The repository helper `./start.ps1 up` starts every application, which is safe but broader than required; the scoped commands above are preferable for this item.

Expected state: dependencies healthy, knowledge-service healthy, and port 8102 bound only to loopback.

Load the API key without displaying it:

```powershell
$line = docker inspect docker-compose-knowledge-service-1 `
  --format '{{range .Config.Env}}{{println .}}{{end}}' |
  Where-Object { $_ -like 'INTERNAL_API_KEY=*' } |
  Select-Object -First 1
$InternalKey = $line.Substring('INTERNAL_API_KEY='.Length)
$Headers = @{ 'X-API-Key' = $InternalKey }
```

Prefer a secret manager or process environment in normal operation. The inspection approach is for local verification only; do not echo `$InternalKey`.

## Endpoint runbook

### 1. Readiness

```powershell
Invoke-RestMethod http://127.0.0.1:8102/health
```

Expected HTTP 200 shape:

```json
{
  "status": "ok",
  "model": "intfloat/multilingual-e5-small",
  "dimensions": 384,
  "collection": "telecom_knowledge",
  "points": 296,
  "checks": {
    "embedder": "ok",
    "qdrant_collection": "ok",
    "retriever": "ok",
    "sparse_embedder": "ok",
    "ce_gate": "ok"
  }
}
```

A 503 with `status=degraded` is an honest readiness failure. Inspect the individual check and logs before proceeding.

### 2. Inventory baseline

```powershell
$Before = Invoke-RestMethod `
  http://127.0.0.1:8102/knowledge/documents `
  -Headers $Headers
$Before | Select-Object total_documents,total_chunks
```

Save these counts. Do not treat archived rows as active: `total_chunks` counts live chunks, while a purged document's archival row remains visible for audit history.

### 3. Create a disposable uniquely named Markdown source

```powershell
$Tag = "rag-runtime-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$Type = "runtime-verification"
$Name = "$Tag.md"
$Source = "$Type/$Name"
$File = Join-Path $env:TEMP $Name
@"
---
title: Disposable RAG Runtime Verification
language: en
document_type: $Type
---
# Disposable runtime verification

This is the unique disposable verification document $Tag.
"@ | Set-Content -Encoding utf8 $File
```

The exact `$Source` is the only source permitted to be purged in this run.

### 4. Upload and unchanged repeat

Windows PowerShell 5.1 lacks `Invoke-RestMethod -Form`; use `curl.exe`:

```powershell
curl.exe -sS -H "X-API-Key: $InternalKey" `
  -F "file=@$File;type=text/markdown" `
  -F "document_type=$Type" `
  -F "auto_ingest=true" `
  http://127.0.0.1:8102/knowledge/upload
```

Expected first response: `status=ingested`, `version=1`, `chunks>=1`, and `indexed>=1`.

Run the identical command again without changing the file. Expected response: `status=unchanged`, same `document_id` and version, `chunks=0`, `indexed=0`. A changed byte sequence intentionally creates a new version; that is not the unchanged test.

### 5. Verify inventory

```powershell
$During = Invoke-RestMethod `
  http://127.0.0.1:8102/knowledge/documents `
  -Headers $Headers
$Target = @($During.documents | Where-Object source -eq $Source)
if ($Target.Count -ne 1 -or $Target[0].status -ne 'ready') {
  throw "Disposable source is not uniquely ready"
}
```

### 6. Retrieval

```powershell
$SearchBody = @{
  query = "comment activer itinérance internationale étranger"
  top_k = 4
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8102/search `
  -Method Post -Headers $Headers `
  -ContentType application/json -Body $SearchBody
```

Runtime-proven expected behavior: HTTP 200 and source-attributed passages. This run returned `procedures/roaming-activation.md` and `contracts/conditions-fup-itinerance-internationale.pdf`. A billing query returned `billing/facturation-factures-gestion-compte.pdf` and `faq/billing-cycle.md`.

A newly indexed synthetic document may still produce an empty result because the score floor, relative cutoff, and CE gate deliberately reject weak candidates. Upload success proves indexing, not relevance. Diagnose with representative domain wording before lowering production thresholds.

### 7. Safe exact-source purge

Safety checks are mandatory:

```powershell
if ($Source -notlike 'runtime-verification/rag-runtime-*.md') {
  throw "Refusing purge: source is not this run's disposable document"
}
$EncodedSource = ($Source.Split('/') | ForEach-Object {
  [uri]::EscapeDataString($_)
}) -join '/'
Invoke-RestMethod `
  "http://127.0.0.1:8102/knowledge/documents/$EncodedSource?remove_object=true" `
  -Method Delete -Headers $Headers
```

Expected: `documents_archived=1`, `chunks_deactivated>=1`, `points_removed>=1`, `object_removed=true`.

Never loop over inventory, purge by title, or purge an existing source. A 404 is safer than substituting another source.

### 8. Post-purge verification

```powershell
$After = Invoke-RestMethod `
  http://127.0.0.1:8102/knowledge/documents `
  -Headers $Headers
$Rows = @($After.documents | Where-Object source -eq $Source)
if ($Rows | Where-Object status -eq 'ready') { throw 'Target still ready' }
if ($After.total_chunks -ne $Before.total_chunks) { throw 'Active chunk baseline not restored' }

# Repeat the disposable query and assert no passage has source == $Source.
Remove-Item $File -ErrorAction SilentlyContinue
```

The document count can increase by one because purge archives the metadata row. The active chunk count and absence from retrieval are the correct cleanup assertions.

## Tests and checks

Executed successfully:

```cmd
set PYTHONPATH=services\knowledge-service\src&& .venv\Scripts\python.exe -m pytest services/knowledge-service/tests packages/service-auth/tests -q
```

Result: **6 passed in 0.42s**.

The agent-worker adapter test could not collect in the root virtual environment because the optional `mcp` package is absent. This does not block the direct knowledge-service workflow. Run it in the agent-worker/container dependency environment:

```powershell
docker compose -f $F -f $A exec agent-worker `
  python -m pytest apps/agent-worker/tests/test_knowledge_toolset_timeout.py -q
```

## Failure modes and troubleshooting

- **403 `invalid internal key`**: use header name `X-API-Key`, not `X-Internal-API-Key`; confirm all containers were recreated after key rotation.
- **503 health, embedder error**: check `/opt/models`, model volume permissions, model/dimension settings, and container logs.
- **503 health, Qdrant error**: verify Qdrant health, URL, collection name, dimensions, and distance metric. Do not serve lexical fallback as if it were RAG.
- **Upload 400**: empty file, unsupported suffix, or file exceeds `KNOWLEDGE_MAX_UPLOAD_MB`.
- **Upload 422**: storage succeeded but parsing/ingestion failed; inspect the returned message and service logs.
- **Upload 503**: PostgreSQL, MinIO, model, or Qdrant pipeline failure. The outbox can preserve replayability, but do not claim the document searchable until inventory/search verifies it.
- **Repeat returns `ingested`**: bytes changed (including encoding/BOM/newlines) or the source key changed. Repeat the exact same bytes, filename, and document type.
- **Search returns 200 with no passages**: candidate scores/gates rejected results. Test known corpus language/domain wording; inspect `KNOWLEDGE_SCORE_FLOOR`, relative cutoff, hybrid settings, and CE threshold. Do not immediately reduce thresholds.
- **Purge leaves inventory row**: expected archival behavior. Assert `status=archived`, zero ready rows for the source, restored active chunk count, removed point/object, and no search hit.
- **Object removal false**: stop; a future bucket scan could re-ingest the object. Verify MinIO endpoint/credentials and retry only the same disposable source.

Useful diagnostics:

```powershell
docker compose -f $F -f $A ps
docker compose -f $F -f $A logs --tail=250 knowledge-service
docker compose -f $F -f $A logs --tail=100 postgres qdrant minio
Invoke-RestMethod http://127.0.0.1:6333/collections/telecom_knowledge
```

## Rollback and cleanup

No code/configuration fix was required. Runtime services were already healthy and were left running in their prior state.

For an interrupted verification, reconstruct only the unique `$Source` recorded by that run and execute the guarded exact-source purge above. Then remove the temporary local file. Never use `docker compose down -v`: it destroys existing PostgreSQL, Qdrant, and MinIO data. To stop containers while preserving volumes:

```powershell
docker compose -f $F -f $A stop knowledge-service
docker compose -f $F -f $A stop postgres qdrant minio
```

## Verification record

- Runtime: Docker 27.3.1; Compose v2.29.7.
- Existing stack: PostgreSQL, Qdrant, MinIO, and knowledge-service healthy.
- Disposable sources were uniquely named under `runtime-verification/` and purged individually.
- Baseline active chunks: 296; upload raised to 297; purge restored 296.
- Purge removed one point and the source object; post-purge retrieval found no disposable source.
- No existing user document was purged.
- No secret value was written to this cookbook or evidence artifacts.

