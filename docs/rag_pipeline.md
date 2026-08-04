# RAG Pipeline — Knowledge Service

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT ARCHITECTURE                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PostgreSQL (knowledge schema)                                           │
│  ├─ knowledge.documents     → versioned source document records          │
│  ├─ knowledge.chunks        → individual text chunks (system of record)  │
│  ├─ knowledge.ingestion_jobs→ auditable ingestion history                │
│  └─ knowledge.sync_outbox   → durable Postgres→Qdrant event queue        │
│                                                                          │
│  MinIO (telecom-knowledge bucket)                                        │
│  └─ Raw source files (PDF/DOCX/CSV/JSON/MD/TXT)                         │
│                                                                          │
│  Qdrant (telecom_knowledge collection)                                   │
│  ├─ Named vector "dense"  → 384d E5 cosine embeddings                   │
│  └─ Named vector "bm25"   → BM25 sparse vectors (IDF weighted)          │
│                                                                          │
│  Knowledge Service (FastAPI :8102)                                       │
│  ├─ POST /search           → the main retrieval endpoint                 │
│  ├─ POST /knowledge/upload → document ingestion via API                  │
│  ├─ GET /knowledge/documents→ corpus inventory                           │
│  ├─ DELETE /knowledge/documents/{source} → purge a document              │
│  └─ GET /health            → readiness probe                             │
│                                                                          │
│  ai-knowledge-rag MCP Server (FastMCP :8201)                             │
│  └─ knowledge_search tool  → proxies to knowledge-service /search        │
│                                                                          │
│  Agent Worker (LiveKit Agent)                                            │
│  ├─ TriageAgent            → has knowledge_search tool                   │
│  ├─ BillingAgent           → has knowledge_search tool                   │
│  └─ TechnicalAgent         → has knowledge_search tool                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## INGESTION PATH

```
  Source Files (MinIO telecom-knowledge bucket)
       │
       ▼
  parsers.py: extract_text()
  ── PDF  → pypdf
  ── DOCX → python-docx
  ── CSV  → csv.DictReader → "col: val; col: val."
  ── JSON → _flatten_json → "path: value"
  ── MD/TXT → raw text
       │
       ▼
  ingestion.py: parse_document()
  ── Front matter → title, language, document_type, extra
  ── Language detection → ar/fr/en script heuristics
       │
       ▼
  ingestion.py: chunk_text()
  ── Paragraph-respecting overlap chunking
  ── 1200 chars max, 150 chars overlap
       │
       ▼
  embeddings.py: embed_passages()  [prepends "passage: "]
  ── intfloat/multilingual-e5-small → 384d dense vectors (ONNX CPU)
  ── Qdrant/bm25 → sparse vectors
       │
       ▼
  PostgreSQL (knowledge schema)
  ├─ documents  (versioned, checksum-guarded)
  ├─ chunks     (system of record; qdrant_point_id links to Qdrant)
  ├─ ingestion_jobs (audit trail)
  └─ sync_outbox    (durable event queue)
       │
       ▼  sync_worker.py drains outbox
  Qdrant (telecom_knowledge collection)
  ├─ "dense" → 384d cosine
  └─ "bm25"  → sparse IDF
```

### Ingestion — Step by Step

| Step | File | Function | Detail |
|------|------|----------|--------|
| **1. Source** | MinIO bucket `telecom-knowledge` | — | Files placed via seed script, HTTP upload, or manual CLI |
| **2. Parse** | `services/knowledge-service/src/knowledge_service/parsers.py` | `extract_text()` | PDF → pypdf, DOCX → python-docx, CSV → prose, JSON → flattened lines, MD/TXT → raw UTF-8 |
| **3. Metadata** | `services/knowledge-service/src/knowledge_service/ingestion.py` | `parse_document()` | Extracts YAML front matter (title, language, type). Falls back to script heuristics for language detection |
| **4. Chunk** | `ingestion.py` | `chunk_text()` | Paragraph-respecting overlap: 1200 chars max, 150 chars overlap. Paragraphs stay intact; oversized paragraphs hard-split |
| **5. Embed** | `services/knowledge-service/src/knowledge_service/embeddings.py` | `embed_passages()` | Dense: `intfloat/multilingual-e5-small` (384d, ONNX CPU) with `passage: ` prefix. Sparse: `Qdrant/bm25` (IDF-weighted) |
| **6. Persist** | PostgreSQL | — | Writes document + chunks + ingestion_job + sync_outbox in one transaction. Checksum guard: identical bytes → no-op |
| **7. Sync** | `services/knowledge-service/src/knowledge_service/sync_worker.py` | — | Drains outbox in batches of 200. Upserts dense + sparse named vectors to Qdrant. Deactivates previous version chunks |

---

## SEARCH PATH

```
  Caller speaks (fr/ar/en)
       │
       ▼
  STT → LLM (Gemini 2.5 Flash)
       │
       ▼
  Agent (Triage/Billing/Technical)
  ── Decides to call knowledge_search tool
       │
       ▼
  LiveKit runs MCP tool via streamable HTTP
  ── knowledge_toolset.py → MCPServerHTTP → ai-knowledge-rag:8201/mcp
       │
       ▼
  ai-knowledge-rag MCP server
  ── knowledge_search.py → POST http://knowledge-service:8102/search
       │
       ▼
  knowledge-service retriever.py
  ── QdrantE5Retriever.search()
       │
       ├─ [1] DENSE E5 SEARCH (gate)
       │     embed_query(query) → "query: ..." → 384d
       │     Qdrant: query_points(using="dense", score_threshold=0.82)
       │     Filter: language=fr, active=True (+ optional filters)
       │     Candidate count: 12
       │     ▼
       │   No hits? → return []
       │
       ├─ [2] BM25 SPARSE SEARCH (co-gate)
       │     embed_query(query) → sparse vector
       │     Qdrant: query_points(using="bm25")
       │     ▼
       │   max_bm25 < SPARSE_MIN? → return []
       │
       ├─ [3] RRF FUSION
       │     Reciprocal Rank Fusion (k=60)
       │     Combines dense + sparse rankings
       │     ▼
       │   Top 4 (or CE max candidates)
       │
       ├─ [3b] CROSS-ENCODER GATE (optional, default ON)
       │     mmarco-mMiniLMv2 → score(query, passage) pairs
       │     Keep if score >= 0.30
       │     On failure → pass through dense+lexical
       │
       ▼
  SearchResponse → list of PassageModel
  ── text, source, score, title, language, document_type, version, metadata
       │
       ▼
  MCP returns to agent
  ── Empty list → "Je n'ai pas cette information"
  ── Has passages → LLM grounds answer, cites source, speaks naturally
       │
       ▼
  TTS plays to caller
```

### Search — Step by Step

| Step | File | Detail |
|------|------|--------|
| **1. Caller speaks** | — | French/Arabic/English → STT → LLM (Gemini 2.5 Flash) |
| **2. Agent tool call** | `apps/agent-worker/src/agents/{triage,billing,technical}_agent.py` | Agent decides to call `knowledge_search` with a concise English query |
| **3. MCP tool** | `apps/agent-worker/src/mcp_clients/knowledge_toolset.py` | `MCPToolset` with `MCPServerHTTP` → `ai-knowledge-rag:8201/mcp`. Only `knowledge_search` exposed |
| **4. MCP proxy** | `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py` | Forwards as `POST /search` with `{"query": ..., "top_k": 4}`. 5s timeout, returns `[]` on failure |
| **5. Dense E5 gate** | `services/knowledge-service/src/knowledge_service/retriever.py` | `embed_query()` with `query: ` prefix → 384d → Qdrant `using="dense"`, threshold 0.82, filter `language=fr + active=True`, fetch 12. No hits → return `[]` |
| **6. BM25 sparse co-gate** | `retriever.py` | Sparse vector → Qdrant `using="bm25"`. Kills keyword-absent noise |
| **7. RRF fusion** | `retriever.py` — `_rrf_fuse()` | Reciprocal Rank Fusion with k=60. Combines dense + sparse rankings into one list |
| **8. Cross-encoder gate** | `services/knowledge-service/src/knowledge_service/ce_gate.py` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (118 MB, ONNX CPU). Joint query-passage scoring. Keep if score ≥ 0.30. On failure → pass through |
| **9. Response** | — | `SearchResponse` with `PassageModel[]` (text, source, score, title, language, version, metadata) |
| **10. Agent reply** | — | Empty → "Je n'ai pas cette information". Has passages → LLM grounds answer, cites source, speaks naturally (no lists/verbatim) |
| **11. TTS** | — | Cartesia sonic-3 synthesizes and plays to caller |

---

## AI Models

| Model | Purpose | Size | Engine | Location |
|-------|---------|------|--------|----------|
| `intfloat/multilingual-e5-small` | Dense passage/query embedding | 118M params | fastembed ONNX CPU | `/opt/models` (baked in Docker) |
| `Qdrant/bm25` | Sparse BM25 embedding | Tiny | fastembed SparseTextEmbedding | Bundled with fastembed |
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Cross-encoder relevance gate | ~118 MB | sentence-transformers, torch-CPU | Downloads at runtime into `/opt/models` |
| `jinaai/jina-reranker-v2-base-multilingual` | (Legacy) Full reranker | ~1.1 GB | fastembed TextCrossEncoder | Baked in Docker (optional, OFF by default) |

All models run locally via ONNX CPU. **Zero external API calls.**

---

## Key Design Decisions

1. **Postgres is the system of record** — Qdrant is a derived, rebuildable index. The `qdrant_point_id` IS the chunk's UUID, enabling reconciliation.
2. **Checksum-based idempotency** — Re-ingesting identical bytes is a no-op. Changed bytes create version N+1 and deactivate the old version.
3. **Honest empty answers** — If no passage clears all gates, an empty list is returned and the agent says it doesn't know, rather than hallucinating.
4. **Three-layer relevance gating** — Dense cosine floor (0.82) kills irrelevant-in-any-language. BM25 sparse min kills keyword-absent noise. Cross-encoder (0.30 threshold) does joint query-passage scoring.
5. **Hybrid retrieval** — Dense (E5) captures semantic meaning; sparse (BM25) captures keyword precision; RRF fuses both without score normalization.
6. **Abstention rule** (`base_agent.py:79`) — Agent MUST ground strictly in returned passages, never guess, and say "Je n'ai pas cette information" if passages don't directly answer.

---

## All Files Involved

### Knowledge Service Core
- `services/knowledge-service/src/knowledge_service/main.py`
- `services/knowledge-service/src/knowledge_service/schemas.py`
- `services/knowledge-service/src/knowledge_service/ingestion.py`
- `services/knowledge-service/src/knowledge_service/embeddings.py`
- `services/knowledge-service/src/knowledge_service/retriever.py`
- `services/knowledge-service/src/knowledge_service/ce_gate.py`
- `services/knowledge-service/src/knowledge_service/qdrant_store.py`
- `services/knowledge-service/src/knowledge_service/minio_store.py`
- `services/knowledge-service/src/knowledge_service/parsers.py`
- `services/knowledge-service/src/knowledge_service/corpus.py`
- `services/knowledge-service/src/knowledge_service/lifecycle.py`
- `services/knowledge-service/src/knowledge_service/sync_worker.py`
- `services/knowledge-service/src/knowledge_service/reindex.py`

### MCP Server (ai-knowledge-rag)
- `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/server.py`
- `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py`

### Agent Worker (MCP Client & Integration)
- `apps/agent-worker/src/mcp_clients/knowledge_toolset.py`
- `apps/agent-worker/src/agents/base_agent.py` (KNOWLEDGE_ABSTENTION_RULE)
- `apps/agent-worker/src/agents/triage_agent.py`
- `apps/agent-worker/src/agents/billing_agent.py`
- `apps/agent-worker/src/agents/technical_agent.py`

### Persistence / Database
- `packages/persistence/src/persistence/models/knowledge.py`
- `packages/persistence/alembic/versions/0010_knowledge_rag.py`

### Domain Core (Port)
- `packages/domain-core/src/domain_core/ports/knowledge.py`

### Scripts
- `scripts/seed_knowledge_bucket.py`
- `scripts/knowledge_score_probe.py`
- `services/knowledge-service/scripts/rag_embedding_ab_check.py`

### Configuration
- `.env.example` (lines 219-311)
