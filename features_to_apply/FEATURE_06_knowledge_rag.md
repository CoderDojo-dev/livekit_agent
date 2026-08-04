# Cookbook 6 — Knowledge Base & RAG (Admin Dashboard)

> Branch target: local `version_80` (HEAD `eda5f58`)
> Scope: `Frontend/admin_dashboard/` only
> Backend files modified: **ZERO**
> Backend files created: **ZERO**
> Status: designed, not applied

---

## §0 — The architecture question, answered from source

At the end of Cookbook 5 I predicted that the read-only escape hatch that saved Tickets would
**not** transfer to Knowledge, because ingestion is inherently a write. That prediction was
half right, and the half that was wrong is more interesting.

Three reads settled it.

**1. Documents DO have a full Postgres projection.**
`packages/persistence/src/persistence/models/knowledge.py` (SHA `c332d985…`) defines four tables
in the `knowledge` schema: `documents`, `chunks`, `ingestion_jobs`, `sync_outbox`. Its module
docstring states the division of labour exactly:

> "PostgreSQL stores document, chunk, ingestion, and synchronization truth. MinIO stores source
> files. Qdrant stores derived searchable vectors."

So, exactly as with `ticketing.tickets`, `business-api` *could* read the corpus inventory straight
out of its own database with a `+1` repository method and a `+1` route, importing nothing new.

**2. But unlike tickets, a purpose-built operator HTTP surface already exists.**
`services/knowledge-service/src/knowledge_service/main.py` (SHA `5ecfac93…`) serves on `:8102` and
already exposes precisely this page's needs. The docstring on `GET /knowledge/documents` is
unambiguous about who it was written for:

> "Inventory of the corpus: what is indexed, in what version, with how many live chunks. Without
> this an operator cannot see what the agent will answer from — and cannot spot that a stray
> upload is outranking real procedures."

That is a description of the admin page in this cookbook. The endpoint was built for it.

**3. Writes are mandatory here, and they are not simple table writes.**
`purge_document()` in `lifecycle.py` (SHA `4c523051…`) is a four-store choreography executed in a
specific, documented order — Postgres, then outbox, then Qdrant, then MinIO — chosen so that a
Qdrant outage still converges instead of stranding data. Upload is comparably orchestrated.

### The decision

**All Knowledge reads and writes go to `knowledge-service` on `:8102` directly from the dashboard's
TanStack server layer. `business-api` is not involved at all, and no backend file changes.**

Why not the Tickets pattern of a `business-api` read method?

Because it would create **two implementations of the same query**. `list_documents()` is not a
trivial select: it left-joins a grouped subquery counting only `active` chunks. If I reimplemented
that join inside `SupervisionRepository`, the dashboard's chunk count and the operator endpoint's
chunk count would be two independently maintained answers to one question. They agree today and
drift tomorrow. "How many chunks is this document contributing to the index" must have exactly one
implementation.

And the reads cannot be separated from the writes here. Upload and purge *must* go through
`knowledge-service`, because it owns MinIO and Qdrant and the outbox ordering. Reading from one
service while writing through another means the page can show a document that the write path
believes it just deleted.

Why not proxy `:8102` through `business-api` (a new set of pass-through routes)?

Rule 3(c) permits new `business-api` endpoints that *expose existing backend functionality to the
frontend*. That clause exists for functionality with no HTTP surface. Here the functionality already
has a correct, owned, documented HTTP surface. Proxying it would add a second network hop, a second
timeout budget, a second failure mode to diagnose, and — decisively — would hand an internal
service credential (`INTERNAL_API_KEY`) to a service that today holds none. That is a real
reduction in security posture in exchange for nothing.

The Feature 0 substrate is already built on "the TanStack server layer holds secrets; the browser
never sees them." Talking to a second internal service from that same server layer is a
continuation of that design, not an exception to it.

**Consequence: Feature 6 is the first feature in this series with real mutations AND zero backend
changes.** Feature 4 and Feature 5 each added backend surface. This one adds none.

---

## §1 — Feature name & scope

**Knowledge Base & RAG** — the `/knowledge` route.

In scope:

- Corpus inventory: every document, its version, live chunk count, language, type, status.
- Index health: whether the corpus is actually searchable right now.
- Upload a source document (PDF/DOCX/CSV/JSON/Markdown) and have it indexed.
- Purge a source document from index, records, and bucket.
- Retrieval probe: run a real query and see exactly what the agent would retrieve.

Out of scope this phase:

- Chunk-level inspection/editing (no endpoint exposes individual chunks).
- Re-ingestion / reindex triggering (`reindex.py` is a CLI concern, no HTTP route).
- Ingestion job history (`knowledge.ingestion_jobs` has no HTTP surface — see §8.3).
- The client/customer portal.

---

## §2 — Backend reference (exact names & paths)

### 2.1 Persistence — `packages/persistence/src/persistence/models/knowledge.py` (`c332d985…`)

**`KnowledgeDocument`** → `knowledge.documents`, mixins `UUIDPrimaryKey, Timestamps, Base`.

| Column | Type | Notes |
|---|---|---|
| `source` | `String(500)` NOT NULL | bucket key, e.g. `tests/env_config.txt` — **contains slashes** |
| `title` | `String(300)` NOT NULL | |
| `language` | `String(20)` NOT NULL default `'und'` | check: `fr, ar, en, multilingual, und` |
| `document_type` | `String(80)` NOT NULL | free taxonomy, becomes the bucket folder |
| `checksum` | `String(64)` NOT NULL | indexed; the re-ingest guard |
| `version` | `Integer` NOT NULL default `1` | check `> 0` |
| `status` | `String(20)` NOT NULL default `'pending'` | check: `pending, processing, ready, failed, archived` |
| `minio_uri` | `Text` NOT NULL | |
| `metadata_json` | `JSONB` (column name `metadata`) | default `{}` |

Constraints that matter to the UI:
`UniqueConstraint(source, version)` — **the same source appears as multiple rows, one per version.**
`Timestamps` mixin supplies `created_at` / `updated_at` (contrast: `Ticket` had no `updated_at`).

**`KnowledgeChunk`** → `knowledge.chunks`. `document_id` FK CASCADE, `ordinal`, `text_content`,
`token_count`, `checksum`, `qdrant_point_id` (unique — the chunk UUID *is* the Qdrant point ID),
`embedding_model`, `embedding_dimensions`, `metadata_json`, **`active`** (bool, default true).
Purge sets `active = False` rather than deleting.

**`KnowledgeIngestionJob`** → `knowledge.ingestion_jobs`. Status `pending|running|succeeded|failed|cancelled`,
plus `document_count`, `chunk_count`, `embedded_count`, `error_details`, `started_at`, `completed_at`.
**No HTTP surface exposes this table.** See §8.3.

**`KnowledgeSyncOutbox`** → `knowledge.sync_outbox`. `operation` `upsert|delete`, status
`pending|processing|succeeded|failed`, `attempt_count`, `available_at`, `last_error`.
The durability net behind Qdrant.

### 2.2 Service — `services/knowledge-service/src/knowledge_service/main.py` (`5ecfac93…`)

Serves on **`0.0.0.0:8102`**. FastAPI app constructed as:

```python
app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)
```

**The entire service is behind an internal API key.** See F2 — this is the single most
important operational fact in this cookbook.

### 2.3 Auth — `packages/service-auth/src/service_auth/__init__.py` (`308311be…`)

```python
def require_internal_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    expected = _expected_key()          # os.getenv("INTERNAL_API_KEY")
    if not expected:
        return                          # auth disabled in dev / tests
    if request.url.path in _HEALTH_PATHS:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden: invalid internal key")
```

`_HEALTH_PATHS = {"/health", "/healthz", "/livez", "/readyz"}`. Header name is **`X-API-Key`**.
Helper `internal_headers()` returns `{"X-API-Key": key}` or `{}`.

### 2.4 Lifecycle — `lifecycle.py` (`4c523051…`)

`list_documents(session)` — left-joins a subquery counting `active` chunks per document,
`order_by(KnowledgeDocument.source.asc(), KnowledgeDocument.version.desc())`, returns dicts with
keys `document_id, source, title, language, document_type, version, status, chunks, checksum`.

`purge_document(session, source, remove_object=True)` — raises `LookupError` when unknown
(→ 404). Otherwise, for **every document row sharing that `source`** (i.e. all versions):
deactivate active chunks, enqueue an outbox `delete` per chunk, set `document.status = "archived"`,
best-effort Qdrant point delete, then MinIO object delete.

Its module docstring is the justification for keeping a destructive control on this page:

> "A single mistaken upload was permanent, and it does not sit quietly: an unrelated file still
> gets embedded, still scores ~0.8 against every question … and still outranks real procedures.
> A corpus you cannot curate degrades with every mistake."

### 2.5 MCP — `mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/server.py` (`f0d690f1…`)

`FastMCP("ai-knowledge-rag", port 8201)`, streamable-http at `/mcp`, registering **one** tool:
`knowledge_search`. Docstring: *"exposing knowledge_search only (review note 1)"*.

This is the **voice agent's** read path. The admin dashboard must not use it: it is a strict
subset of the service surface, it has no inventory or lifecycle capability, and routing a browser
feature through an MCP transport adds a protocol for no gain.

---

## §3 — Endpoints

### 3.1 Existing, to reuse — all on `knowledge-service` `:8102`

Every one requires header `X-API-Key: ${INTERNAL_API_KEY}` when that env var is set.

#### `GET /health`

Exempt from the key check. Returns:

```jsonc
{
  "status": "ok" | "degraded",
  "model": "...",              // embedder.model_name
  "dimensions": 1024,           // embedder.dimensions
  "collection": "...",          // qdrant_collection()
  "points": 12345,              // int | null  — live vector count
  "checks": {
    "embedder": "ok" | "error: ...",
    "qdrant_collection": "ok" | "error: ...",
    "retriever": "ok" | "error: ...",
    "sparse_embedder": "ok" | "error: ...",   // only when hybrid_enabled()
    "ce_gate": "ok" | "warming" | "disabled"
  }
}
```

HTTP **503** when not ready. Readiness explicitly **excludes** `ce_gate`:
`ready = all(v == "ok" for k, v in checks.items() if k != "ce_gate")`.
So `ce_gate: "warming"` is normal and must not be rendered as a fault.

#### `GET /knowledge/documents`

No parameters. No pagination. Returns `DocumentListResponse`:

```jsonc
{
  "documents": [
    {
      "document_id": "uuid-string",
      "source": "procedures/roaming.pdf",
      "title": "",            // may be empty string
      "language": "",          // fr | ar | en | multilingual | und
      "document_type": "",
      "version": 1,
      "status": "",            // pending | processing | ready | failed | archived
      "chunks": 0,             // live (active) chunk count
      "checksum": ""
    }
  ],
  "total_documents": 0,
  "total_chunks": 0
}
```

**No timestamp field.** See F5.

#### `POST /knowledge/upload` — multipart/form-data

| Field | Kind | Default |
|---|---|---|
| `file` | `UploadFile`, required | — |
| `document_type` | `Form(str)` | `"general"` |
| `auto_ingest` | `Form(bool)` | `True` |

Returns `UploadResponse`:

```jsonc
{
  "source": "general/roaming.pdf",
  "status": "ingested" | "unchanged" | "stored" | "failed",
  "document_id": "uuid" | null,
  "version": 0,
  "chunks": 0,
  "indexed": 0,
  "message": ""
}
```

Error mapping, taken from the handler:

| Condition | Status |
|---|---|
| `ValueError` — unsupported format / empty / too large | **400** |
| any other exception — storage or pipeline | **503** |
| `result["status"] == "failed"` | **422**, `detail = result["message"]` |

So `"failed"` never arrives as a 200 body; it arrives as a 422 error.

#### `DELETE /knowledge/documents/{source:path}`

Query param `remove_object: bool = True`. Returns `PurgeResponse`:

```jsonc
{
  "source": "...",
  "documents_archived": 0,
  "chunks_deactivated": 0,
  "points_removed": 0,
  "object_removed": false
}
```

**404** when the source is unknown (`LookupError`), **503** on failure.

#### `POST /search`

Non-mutating despite the verb. Body `SearchRequest`:
`query` (required), `top_k` (default 4), `language`, `document_type`, `region`,
`applicable_plans[]`, `product_codes[]`, `min_score`.

Returns `{ "passages": [ { text, source, score, title, language, document_type, version, metadata } ] }`.
**503** when the index is unusable — deliberately, rather than degrading to term overlap.

### 3.2 New endpoints to create

**None.** No backend file is modified or created by this cookbook.

### 3.3 CORS / middleware

No change. The browser never contacts `:8102`; the dashboard's server layer does.
The `business-api` CORS block is untouched and irrelevant here.

---

## §4 — Findings

### F1 — The corpus has a Postgres projection, but the service is the right client

Covered in §0. The operative rule for the rest of this series: *a Postgres projection makes a
direct read **possible**; an owned HTTP surface with non-trivial query logic makes it **wrong**.*
Tickets had a projection and no estate-wide HTTP read (`lookup_tickets` is per-customer only), so
the direct read won. Knowledge has both, so the service wins.

### F2 — ⚠️ The dev/prod auth trap: this will work on your machine and 403 in staging

`require_internal_key` is **opt-in**:

> "It is intentionally **opt-in**: if the env var is unset (dev / tests), the dependency is a
> no-op and clients send no header — so nothing breaks locally. In staging/prod, set the key
> everywhere and every internal call must present `X-API-Key`."

This is the highest-risk item in the feature, and it is risky *precisely because it is convenient*.
A developer with no `INTERNAL_API_KEY` set will build the whole page, see it work end to end, pass
every local test, and ship something that returns 403 on every request the moment it reaches an
environment where the key is set.

**Mitigations, all mandatory:**

1. `knowledgeApi()` sends `X-API-Key` **whenever `INTERNAL_API_KEY` is present in the dashboard's
   server env**, and omits it when absent — mirroring `internal_headers()` exactly. Never
   conditionally on `NODE_ENV`.
2. `.env.example` gains `INTERNAL_API_KEY=` with a comment stating that leaving it blank is only
   valid if the knowledge-service also has it blank, and that the two must match.
3. A 403 from `:8102` is surfaced with a **specific** message — "knowledge-service rejected the
   internal key" — not folded into the generic network error. A generic message here would send
   someone hunting a networking problem that does not exist.

### F3 — Status mapping trap, fourth recurrence, and this time it hits the *normal* row

`documents.status` ∈ `pending | processing | ready | failed | archived`.

`status.ts` (`84449b29`) contains `pending`, `processing`, `failed`, `archived` — and **not**
`ready`. It does contain **`indexed`**, which is plainly the intended key for this exact concept.

`StatusChip` is `const def = STATUS[status]; if (!def) return null;` — an unknown key renders
**nothing at all**, silently.

Four of five values map by identity. The fifth, `ready`, is the **steady state of every healthy
document** — so a naive pass-through produces a table where the broken rows show a chip and the
healthy majority show blank space. That reads as "most documents have no status", which is the
opposite of the truth.

**Mapping (total, no fallthrough):**

| Backend | `status.ts` key |
|---|---|
| `ready` | **`indexed`** |
| `pending` | `pending` |
| `processing` | `processing` |
| `failed` | `failed` |
| `archived` | `archived` |

Implemented as `documentStatusKey()` with an explicit `Record`, defaulting unknown input to
`pending` rather than passing it through. Do **not** inline `<StatusChip status={d.status} />`.

### F4 — The same source appears multiple times, and the mock's React key is a bug

`UniqueConstraint(source, version)` plus versioned re-ingestion means one logical document is N
rows. `list_documents` orders `source ASC, version DESC`, so versions of a source sit adjacent,
newest first.

The mock does `KNOWLEDGE_SOURCES.map((s) => <tr key={s.name}>)`. Against real data that produces
**duplicate React keys** the first time anyone re-uploads a file — with the usual consequence of
rows reconciling incorrectly during re-render.

**Fix:** key on `document_id`, which is a UUID and unique by construction.

**Additional consequence:** after a few re-ingests, most rows are `archived` noise. Ship a
**"Hide archived"** toggle, **default ON**. Implemented as a client-side filter (the endpoint has
no parameters), and the footer must then report both numbers so hiding never looks like data loss.

### F5 — The "Updated" column has no data; replace it with Version

`KnowledgeDocument` carries the `Timestamps` mixin, so `created_at`/`updated_at` exist in the
database. But `DocumentSummary` — the wire DTO — has no timestamp field, and `list_documents`
does not project one. The data exists and is not exposed.

Options considered:

- **(a) Add `updated_at` to `DocumentSummary` + `list_documents`.** Two-line backend change,
  genuinely small. Rejected: it modifies a service this cookbook otherwise leaves untouched, and
  it changes a DTO shared with the CLI/operator tooling. Not worth it unilaterally — raised as
  §8.1 instead.
- **(b) Drop the column.** Loses a slot on a four-column table.
- **(c) Replace with `version`.** ✅ Chosen.

`version` is always present, always meaningful, and answers a question an operator genuinely has:
*v3 means this source has been re-ingested twice.* Right-aligned, `t-mono`, rendered `v{n}`,
mirroring Feature 3's `P{n}` treatment of `priority_level`.

This is the same manoeuvre as Feature 5's Advisor→Category swap: remove a column with no backing
data, put a real one in the freed slot, rather than leaving a permanently empty column.

### F6 — `source` is the identifier; `title` is decoration and often empty

`title` is `String(300)` NOT NULL in the model but defaults to `""` in the DTO, and nothing
guarantees the ingester populates it. `source` is NOT NULL, unique per version, and — critically —
is **the path parameter of the DELETE endpoint**. It is the real identity.

**Render:** `source` as the primary cell in `t-mono text-ink-1` (matching the mock's treatment),
with `title` beneath in `t-caption text-ink-4` **only when non-empty and different from `source`**.
Never render an empty title row — that produces a ragged column of blank second lines.

### F7 — ⚠️ `source` contains slashes; naive encoding breaks the DELETE

The route is `DELETE /knowledge/documents/{source:path}` and the docstring is explicit:

> "`source` is the bucket key (e.g. `tests/env_config.txt`), so it contains slashes — hence the
> `:path` converter."

`encodeURIComponent("tests/env_config.txt")` yields `tests%2Fenv_config.txt`. Depending on proxy
and ASGI normalisation, that either fails to match the route or matches a literal-percent source
that does not exist — in both cases surfacing as a **404 that looks like "document not found"**
when the document is right there in the table.

**Rule:** encode **per segment**, preserving separators:

```ts
const encodeSourcePath = (source: string) =>
  source.split("/").map(encodeURIComponent).join("/");
```

This preserves the slashes the `:path` converter needs while still escaping spaces, `#`, `?` and
non-ASCII inside each segment. Filenames with spaces are common; this is not a theoretical concern.

### F8 — ⚠️ Purge is genuinely destructive and irreversible — but must stay

`purge_document(..., remove_object=True)` archives the Postgres rows, deactivates chunks, deletes
Qdrant points, **and deletes the object from the MinIO bucket**. The source file is gone. There is
no soft-delete of the object and no undo.

Contrast with Feature 5, where I *removed* the "New ticket" button because its side effect
(WhatsApping a customer) was both surprising and unwanted. Here the destructive action is the
opposite: it is the documented reason the module exists, and the absence of curation actively
degrades every answer the agent gives.

So the control stays — behind friction proportional to the consequence:

- A `Modal` (Feature 1's, portalled to `document.body`) — never a bare `confirm()`.
- The user must **type the exact `source`** to enable the confirm button. Not a checkbox; typing
  forces the eye over the identifier and makes wrong-row deletion nearly impossible.
- The modal states plainly, in body copy, that the file is removed from the storage bucket as well
  as the index, and cannot be recovered.
- The confirm button is `variant="primary"` — there is no destructive variant in `primitives.tsx`
  and **inventing one would breach the locked design system.** The typed confirmation carries the
  weight instead. Flagged as §8.6.

We always send `remove_object=true` (the default). Not deleting the object is a trap: an archived
document no longer matches the `status='ready'` checksum guard, so a file left in the bucket is
**re-ingested as a new version on the next scan** — the deletion would silently undo itself.
`lifecycle.py` says so directly. Exposing a "keep the file" checkbox would be offering a footgun.

### F9 — Upload has four outcomes and three of them are not "success"

`UploadResponse.status` ∈ `ingested | unchanged | stored | failed`.

| Value | Meaning | UI |
|---|---|---|
| `ingested` | stored, chunked, embedded, searchable now | success — "Indexed — {chunks} chunks" |
| `unchanged` | checksum matched an existing document; nothing done | **neutral** — "Already indexed — unchanged" |
| `stored` | in the bucket, **not** searchable | **warning** — only reachable if `auto_ingest=false` |
| `failed` | arrives as HTTP **422**, not a 200 body | error path |

`unchanged` is the one that matters. Re-uploading the same file is a legitimate, frequent action
("did this get in?"), and reporting it as "Uploaded successfully" teaches the operator that upload
worked when nothing happened. Reporting it as failure is equally wrong. It needs its own neutral
wording.

We always send `auto_ingest=true`, so `stored` should be unreachable — handle it anyway rather
than letting it fall through to a default success message.

### F10 — 503 is a designed answer, not an outage; the UI must not flatten it

The service philosophy is stated twice, in `main.py`:

> "`/search` is dense-only … When the index is unusable it returns 503 instead of quietly serving
> term-overlap results that look like RAG but are not."

> "Never fall back to term overlap: a plausible wrong answer is worse than a clear failure."

The frontend must honour the same principle. Specifically:

- **A 503 on the document list must never render as an empty table.** "No documents indexed" and
  "the index is unreachable" are opposite facts; conflating them tells an operator their corpus is
  empty when it may be full. 503 → `ErrorState` with a retry.
- `EmptyState` renders **only** on a 200 with `documents.length === 0`.
- The health banner (F11) is what distinguishes the two at a glance.

### F11 — `/health` is a real readiness probe and deserves surfacing

> "`/health` is a real readiness probe, not a liveness lie: it proves the embedding model loads and
> emits the configured width, and that the Qdrant collection exists with a matching dimension and
> distance."

It is the only place that answers "is the agent's knowledge actually searchable right now", and it
returns `points` — the live vector count, which is an independent cross-check on the sum of
`chunks` in the inventory. A large divergence between `total_chunks` and `points` means Postgres
and Qdrant have drifted and the outbox is behind.

Rendered as a compact `Card` strip above the table: status, model, dimensions, collection, points.
Degraded state lists the failing `checks` keys.

`ce_gate` is **excluded from readiness by the backend** and may legitimately read `"warming"`.
Rendering it as a fault would produce a permanent false alarm on every cold start. It is shown, if
at all, as neutral informational text — never red, never counted in the degraded set.

### F12 — Ordering is alphabetical, and the docstring says otherwise

`list_documents` docstring: *"Every document in the corpus with its live chunk count, **newest
source first**."*

The actual clause: `.order_by(KnowledgeDocument.source.asc(), KnowledgeDocument.version.desc())`.

That is **alphabetical by source**, then newest version first *within* a source. There is no
recency ordering across sources at all — `created_at` is not in the ORDER BY. The docstring is
wrong.

**Decision: preserve the server's ordering; do not client-side re-sort.** The operator CLI and this
page should agree on row order, and grouping versions adjacently is genuinely useful. Logged as a
docstring defect in §8.4 — not fixed here, since this cookbook modifies no backend file.

### F13 — Use the server's totals, not client-side arithmetic

`DocumentListResponse` supplies `total_documents` and `total_chunks`. Use them verbatim in the
footer. Recomputing `documents.length` client-side would diverge the moment the "Hide archived"
filter is applied — the footer would silently start reporting the filtered count as the corpus size.

Footer reads: `{total_documents} documents · {total_chunks} chunks indexed`, plus, when the filter
is active, `({n} archived hidden)`.

### F14 — `language: "und"` means undetermined; do not print it

The check constraint allows `und` and it is the server default. Rendering the literal string `und`
in a table exposes an internal sentinel. Map `und` and `""` to an em-dash. `multilingual` renders
as "Multilingual"; `fr`/`ar`/`en` uppercase to `FR`/`AR`/`EN`.

### F15 — No pagination on the inventory endpoint

`GET /knowledge/documents` takes no parameters and returns the entire corpus in one response. Fine
at current scale and not something to work around client-side. Noted in §8.5 so it is a known
ceiling rather than a surprise.

### F16 — The retrieval probe is the highest-value addition on this page

`POST /search` lets an admin ask: *what would the agent actually retrieve for this question?* That
is the only way to verify the "stray upload outranking real procedures" failure the lifecycle
docstring warns about — the inventory table alone cannot reveal it, because a poisoning document
looks perfectly healthy in a list.

It directly serves the "RAG system" half of the requested scope, beyond ingestion. Included as a
second `PageSection`.

Implementation notes:
- POST, but **non-mutating** — it is a query, and must not invalidate any cache.
- Default `top_k = 4`, matching `SearchRequest`'s default (the value the agent actually uses).
- **Send no filters.** `SearchRequest.filters()` drops unset keys, and the schema warns
  explicitly: *"filtering by `language` in particular is usually wrong here, because the corpus is
  English while callers speak fr/ar/en and E5's aligned space is what lets a French question find
  an English procedure."* Offering a language filter in the UI would invite exactly the mistake
  the backend author documented.
- **Do not add a score threshold control.** *"E5 cosine scores cluster ~0.7–1.0 … a threshold
  copied from another model will either filter nothing or everything."* Leave `min_score` unset.
- Display the raw score to 3 decimals with no colour-coding — given the ~0.7–1.0 clustering, a
  green/red treatment would imply a confidence distinction that does not exist.

### F17 — `data.ts` removals must be grep-guarded

Targets: `KNOWLEDGE_SOURCES` (used by `knowledge.tsx`) and `INGESTED_FILES` (importer unknown).
Per the Feature 4 lesson, run first:

```bash
grep -rn "KNOWLEDGE_SOURCES\|INGESTED_FILES" src/
```

Remove **only** symbols whose sole importer was `knowledge.tsx`. If `INGESTED_FILES` is imported
anywhere else, leave it. No name collision this time (unlike Feature 5's `TicketRow`), but verify
rather than assume.

### F18 — No route or navigation change

`/knowledge` already exists in `routeTree.gen.ts`, in `nav.ts` (KNOWLEDGE section), and in
`PAGE_META`. The file is rewritten in place. **`routeTree.gen.ts` and `nav.ts` must show zero diff.**
No new keyboard shortcut is needed or taken.

### F19 — There is no file-input primitive; do not create a styled one

`primitives.tsx` has no file input. Building a new styled file-drop control would introduce new
visual language and breach the locked design system.

**Pattern:** a visually hidden `<input type="file">` driven by the existing `Button icon={Upload}`
via a ref. The `Button` renders exactly as the mock's already does. The chosen filename displays in
`t-caption text-ink-3` beside it. `document_type` uses the existing `TextField` (added in
Feature 0), defaulting to `"general"` to match the `Form` default.

No new tokens, no new component shapes, no `<label>` restyling.

### F20 — CSRF: the delete server function must be POST

The Feature 2 correction applies unchanged: React Start's CSRF protection requires every mutating
server function to be declared `createServerFn({ method: "POST" })`. The real `DELETE` verb is
emitted downstream by `knowledgeApi`. Upload is POST at both layers, so only purge is affected.

### F21 — Multipart cannot go through the JSON helper

`businessApi<T>()` serialises JSON. Upload is `multipart/form-data` and the boundary must be set by
the runtime, **not** by us. `knowledgeApi` therefore takes an optional `body: FormData` branch
that: passes the `FormData` straight through, and **omits `Content-Type` entirely** so `fetch`
generates the boundary. Manually setting `Content-Type: multipart/form-data` without a boundary is
the classic failure here and produces a confusing 422 from FastAPI.

---

## §5 — Frontend implementation plan

### 5.1 Files

| Action | Path |
|---|---|
| **new** | `src/lib/api/knowledge.server.ts` |
| **new** | `src/lib/nexus/knowledge-view.ts` |
| **new** | `src/components/nexus/knowledge-upload.tsx` |
| **new** | `src/components/nexus/knowledge-purge.tsx` |
| **new** | `src/components/nexus/retrieval-probe.tsx` |
| **modified** | `src/lib/nexus/query-keys.ts` — append `knowledgeKeys` |
| **modified** | `src/lib/nexus/data.ts` — guarded removal (F17) |
| **modified** | `.env.example` — add `KNOWLEDGE_API_URL`, `INTERNAL_API_KEY` |
| **rewritten** | `src/routes/knowledge.tsx` |

**Unchanged, must show zero diff:** `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx`,
`blocks.tsx`, `modal.tsx`, `format.ts`, `styles.css`, and every file under `src/lib/api/` other
than the new one.

### 5.2 `src/lib/api/knowledge.server.ts`

Mirrors `business-api.ts` in shape and error taxonomy — same `ApiError`, same helpers — so the page
reuses `errorMessage()`, `isForbidden()` and the existing state components unchanged.

Exports:

- `knowledgeApi<T>(path, { method, query, body, formData })` — internal transport.
  - Base URL from `process.env.KNOWLEDGE_API_URL` (default `http://localhost:8102`).
  - Adds `X-API-Key` **iff** `process.env.INTERNAL_API_KEY` is set (mirrors `internal_headers()`).
  - `formData` branch omits `Content-Type` (F21).
  - Timeout via `AbortController`, reusing `BUSINESS_API_TIMEOUT_MS` semantics under
    `KNOWLEDGE_API_TIMEOUT_MS`; embedding on a cold model is slow, so default it higher — **60000 ms**.
  - Maps 403 to an `ApiError` whose message names the internal key explicitly (F2).
- `listDocuments` — `createServerFn({ method: "GET" })`, `requireRole("superviseur")`.
- `knowledgeHealth` — `createServerFn({ method: "GET" })`, `requireRole("superviseur")`.
- `uploadDocument` — `createServerFn({ method: "POST" })`, `requireRole("administrateur")`.
- `purgeDocument` — `createServerFn({ method: "POST" })`, `requireRole("administrateur")`,
  emitting `DELETE` downstream (F20), path built with `encodeSourcePath` (F7).
- `probeSearch` — `createServerFn({ method: "POST" })`, `requireRole("superviseur")`.

Types: `KnowledgeDocumentRow`, `KnowledgeDocumentList`, `KnowledgeHealth`, `UploadResult`,
`PurgeResult`, `Passage`, `ProbeResult`.

**Role split rationale.** Reads at `superviseur` matches every other read surface in this series.
Upload and purge are set to `administrateur` because purge is irreversible across three stores and
upload changes what the agent tells customers. `requireRole` is a **factory** — `requireRole("administrateur")` —
per the Feature 2 correction; copy the composition from `availability.server.ts`, not from this
cookbook's prose.

### 5.3 `src/lib/nexus/knowledge-view.ts`

Pure functions, no JSX, no network:

- `documentStatusKey(status: string): StatusKey` — total map, F3.
- `languageLabel(code: string): string` — `und`/`""` → `"—"`, F14.
- `documentTypeLabel(t: string): string` — `""` → `"—"`, otherwise title-cased.
- `encodeSourcePath(source: string): string` — F7.
- `isArchived(d): boolean`.
- `visibleDocuments(docs, hideArchived): KnowledgeDocumentRow[]`.
- `archivedCount(docs): number`.
- `uploadOutcome(r: UploadResult): { tone: "success" | "neutral" | "warning"; message: string }` — F9.
- `healthSummary(h): { ready: boolean; failing: string[] }` — excludes `ce_gate`, F11.
- `formatScore(n: number): string` — 3 decimals, F16.

Keeping these pure means each is unit-testable without a running backend — the same split that let
Feature 2 ship 26 pure tests alongside its live suite.

### 5.4 `query-keys.ts` addition

```ts
export const knowledgeKeys = {
  all: ["knowledge"] as const,
  documents: () => [...knowledgeKeys.all, "documents"] as const,
  health: () => [...knowledgeKeys.all, "health"] as const,
};
```

The probe is **not** keyed — it is a user-triggered mutation-shaped query whose results must never
be cached or replayed, and must never invalidate the inventory.

After a successful upload or purge, invalidate **both** `documents()` and `health()` — `points`
changes too, and a stale health strip after an upload is exactly the kind of quiet inconsistency
this series has been eliminating.

### 5.5 `src/routes/knowledge.tsx` — structure

Three `PageSection`s, in order:

**1. Index health strip** — a `Card` (not `StatCard`: `delta` is non-optional and there is no
honest delta here — the Feature 5 finding F9 applies unchanged). Values in `t-metric-m`, labels in
`t-micro`: Status · Model · Dimensions · Points · Collection. On degraded, the failing check keys
list beneath in `t-caption`.

**2. Corpus inventory** — `TableShell`, preserving the mock's toolbar composition exactly:
`SearchInput placeholder="Search sources" className="w-[260px]"` (client-side filter over `source`
and `title`), a `Segmented` "Hide archived" toggle, and the existing
`Button icon={Upload} size="sm" variant="primary" className="ml-auto"`.

Columns — mock had `Source | Chunks | Updated | Status`:

| Column | Align | Source of truth |
|---|---|---|
| Source | left | `source` in `t-mono text-ink-1`; `title` beneath in `t-caption text-ink-4` when present and different (F6) |
| Type | left | `documentTypeLabel` |
| Lang | left | `languageLabel` (F14) |
| Chunks | right | `Token` — unchanged from mock |
| **Version** | right | `t-mono text-ink-3`, `v{n}` — **replaces "Updated"** (F5) |
| Status | left | `StatusChip status={documentStatusKey(d.status)}` (F3) |
| — | right | purge `IconButton`, `administrateur` only |

Row: `key={d.document_id}` (F4), preserving
`className="transition-colors duration-[120ms] hover:bg-surface-3"`.

States: `TableSkeleton rows={8} cols={7}` while loading · `TableErrorRow` on error, with a
key-specific message on 403 (F2) · `EmptyState` **only** on a 200 with zero documents (F10).

Footer: F13.

**3. Retrieval probe** — `Card` with `CardHeader title="Retrieval probe"`, subtitle explaining it
runs the same query path the agent uses. A `TextField` + `Button`, then results as a compact list:
rank, score (`t-mono`), source (`t-mono`), and the passage text in `t-ui text-ink-2` clamped to a
few lines. 503 → `InlineError` stating the index is unusable, never an empty result list (F10).

### 5.6 Upload flow — `knowledge-upload.tsx`

`Modal` (portalled, per the Feature 1 defect). Contents: hidden file input + `Button` trigger (F19),
chosen filename, `TextField` for `document_type` default `"general"`, and Cancel / Upload.

On submit: build `FormData` with `file`, `document_type`, `auto_ingest = "true"`.

Submit button disabled while pending, with the copy changed to "Indexing…" — parsing and embedding
are CPU-bound and run in a threadpool; a large PDF takes real time and an unchanged label reads as
a frozen dialog.

On success: close, invalidate both keys, surface `uploadOutcome()` (F9) — note that
`unchanged` closes with a neutral message, not a success one.
On 400: keep the modal open, show `InlineError` with the server's `detail` (it names the actual
rejection — unsupported format, empty, too large) rather than a generic message.
On 422/503: keep open, `InlineError`.

### 5.7 Purge flow — `knowledge-purge.tsx`

`Modal`. Body states the source, and that this removes it from the index, the records, **and the
storage bucket**, permanently. `TextField` requiring the exact `source` string; confirm disabled
until it matches exactly (F8). On 404, report that the source is already gone and invalidate the
list — the table was stale.

### 5.8 Data flow summary

```
browser ──▶ TanStack server fn (requireRole)
                 │  X-API-Key: INTERNAL_API_KEY   (when set)
                 ▼
         knowledge-service :8102
                 │
     ┌───────────┼────────────┬──────────┐
     ▼           ▼            ▼          ▼
  Postgres    Qdrant       MinIO      outbox
```

The browser makes **zero** direct requests to `:8102` and **zero** to `:8108`. `INTERNAL_API_KEY`
never reaches the client bundle — which is enforced structurally by the `.server.ts` suffix, since
TanStack Start's import-protection rejects importing server primitives into a client bundle.

---

## §6 — Design-system compliance

| Constraint | Status |
|---|---|
| New colours | none — `StatusChip` and existing `text-ink-*` only |
| New spacing / radius / type tokens | none |
| New component shapes | none — `Card`, `TableShell`, `Modal`, `TextField`, `Button`, `IconButton`, `Token`, `StatusChip`, `Segmented`, `SearchInput`, `EmptyState` |
| New npm dependencies | **zero** |
| New `status.ts` keys | **zero** — `ready` maps onto existing `indexed` |
| `StatCard` used | no — `delta` is non-optional and no honest delta exists (Feature 5 F9) |
| Destructive button variant | **not invented** — typed confirmation instead (F8) |
| File-input control | hidden input + existing `Button` (F19) |
| Fixed/overlay elements | via `Modal`, which portals to `document.body` (Feature 1 defect 3) |
| Navigation / routes | unchanged (F18) |
| Lint baseline | must return to exactly **36 problems** |

---

## §7 — Validation checklist

**Static**

- [ ] `tsc --noEmit` clean.
- [ ] `eslint` returns exactly the 36-problem baseline — no more, no fewer.
- [ ] `build` exit 0.
- [ ] `git diff --stat` shows **zero** backend files.
- [ ] `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx`, `blocks.tsx` all show zero diff.
- [ ] `grep -rn "8102" src/` → hits only in `knowledge.server.ts` and `.env.example`.
- [ ] `grep -rn "INTERNAL_API_KEY" src/` → hits only in `.server.ts` files and `.env.example`.
- [ ] `grep -rn "KNOWLEDGE_SOURCES\|INGESTED_FILES" src/` → empty after removal, or justified.
- [ ] No raw hex or `rgb(` introduced anywhere.

**Behavioural**

- [ ] Table renders; a `ready` document shows the **indexed** chip, not blank space (F3).
- [ ] `pending`, `processing`, `failed`, `archived` each render a chip.
- [ ] A source with two versions renders two rows, no duplicate-key warning in console (F4).
- [ ] "Hide archived" defaults ON; toggling reveals archived rows; footer reports both counts (F13).
- [ ] A source containing a slash purges successfully — not a 404 (F7).
- [ ] A source containing a space purges successfully (F7).
- [ ] Purge confirm stays disabled until the source is typed exactly (F8).
- [ ] Upload of a supported file → `ingested`, chunk count shown, table and health both refresh.
- [ ] **Re-upload of the identical file → `unchanged`, neutral message, not "success"** (F9).
- [ ] Upload of an unsupported format → 400 with the server's own detail text.
- [ ] `language: "und"` renders `—`, never the literal `und` (F14).
- [ ] Empty title does not render a blank second line (F6).
- [ ] Probe returns passages with scores; `top_k` defaults to 4.
- [ ] Probe sends no `language`, no `document_type`, no `min_score` (F16).

**Failure modes**

- [ ] Stop `knowledge-service`: table shows `ErrorState` with retry — **not** an empty table (F10).
- [ ] With `INTERNAL_API_KEY` set on the service but **not** in the dashboard env: every call 403s
      and the message names the internal key, not a generic network error (F2). *Run this test —
      it is the one the local environment will otherwise hide.*
- [ ] With the key set correctly in both: everything works.
- [ ] Degraded index (`/health` 503): banner shows degraded and lists failing checks.
- [ ] `ce_gate: "warming"` does **not** show as degraded (F11).
- [ ] Probe against a degraded index → clear 503 message, never an empty passage list (F10).
- [ ] `conseiller` role: reads 403 as designed; upload/purge controls absent, not merely disabled.

**Network discipline**

- [ ] DevTools shows **zero** browser requests to `:8102`.
- [ ] DevTools shows **zero** browser requests to `:8108`.
- [ ] No `X-API-Key` string anywhere in the client bundle: `grep -r "X-API-Key" dist/` → empty.

---

## §8 — Open questions

**§8.1 — Expose `updated_at` on `DocumentSummary`?**
The data exists on the model via `Timestamps` but is not projected into the DTO. Adding it is a
two-line change to `lifecycle.py` and `schemas.py`, and it would restore a genuine "Updated"
column. I did not take it unilaterally: it changes a DTO shared with operator tooling, and this
cookbook otherwise touches no backend file. Shipped as **Version** instead (F5). Say the word and
it becomes a two-line patch.

**§8.2 — Should upload/purge be `administrateur` or `superviseur`?**
I chose `administrateur` because purge is irreversible across three stores. If supervisors are
expected to curate the corpus day to day, this is a one-line change per server function. Reads stay
`superviseur` either way.

**§8.3 — Surface ingestion job history?**
`knowledge.ingestion_jobs` records every attempt with `error_details`, `started_at`, `completed_at`
and embedded counts — genuinely useful for diagnosing a failed upload. **No HTTP surface exposes
it.** Options: a new `knowledge-service` route (its rightful owner), or a `business-api` read
(the table is in the same Postgres). Not built, because it needs new backend surface and the
upload flow already surfaces per-upload errors inline.

**§8.4 — `list_documents` docstring is wrong** (F12). It claims "newest source first"; the query
orders `source ASC, version DESC`. Docstring fix, no behaviour change. Want it corrected?

**§8.5 — No pagination on the inventory** (F15). Fine now; a corpus in the thousands will make this
page heavy. Adding `limit`/`offset` is a `knowledge-service` change.

**§8.6 — No destructive button variant exists in the design system** (F8). The typed confirmation
carries the weight instead. If you want a destructive treatment, it must be added to `status.ts`
and `primitives.tsx` deliberately as a design-system decision — not improvised inside a feature.

**§8.7 — Should the probe be visible to `conseiller`?**
It is read-only and a good support tool ("what does the agent know about X?"). Currently
`superviseur`. Easy to widen.

**§8.8 — Cross-link passages to inventory rows.**
`PassageModel.source` matches `DocumentSummary.source`, so a probe hit could deep-link to its row
— making "this stray upload is outranking real procedures" a two-click diagnosis. Deferred: it
needs a row-anchor scheme this page does not yet have.

**§8.9 — `total_chunks` vs `/health` `points` divergence.**
These count the same thing in two stores. A persistent gap means the outbox is behind or Qdrant
drifted. Worth a visible warning when they differ by more than a small margin — but I do not know
the expected steady-state delta, so I did not invent a threshold. What is normal in your
environment?

---

## §9 — Diff summary

```
 Frontend/admin_dashboard/
   src/lib/api/knowledge.server.ts          | new
   src/lib/nexus/knowledge-view.ts          | new
   src/components/nexus/knowledge-upload.tsx| new
   src/components/nexus/knowledge-purge.tsx | new
   src/components/nexus/retrieval-probe.tsx | new
   src/lib/nexus/query-keys.ts              | +knowledgeKeys
   src/lib/nexus/data.ts                    | -KNOWLEDGE_SOURCES (grep-guarded)
   src/routes/knowledge.tsx                 | rewritten
   .env.example                             | +KNOWLEDGE_API_URL +INTERNAL_API_KEY
                                            |   +KNOWLEDGE_API_TIMEOUT_MS

 backend                                    | 0 files changed
```

Zero new npm dependencies · zero new tokens · zero new status keys · zero route changes ·
zero navigation changes · zero backend changes · zero CORS changes.

---

## §10 — Next feature

**Guardrails / Policies** (`/policies`, `/rules`).

Known from prior extraction: `business-api` already serves
`GET /policy/verdicts?session_id=` (`superviseur`) and `GET /reference/business-rules`
(`administrateur`), backed by `SupervisionRepository.verdicts()` and `business_rules()`, over
`persistence.models.policy.PolicyVerdict` and `reference.BusinessRule`.

The decisive question for Cookbook 7 mirrors the one this cookbook just answered: **the user asked
for guardrails "viewing + possibility of modification", and both existing endpoints are reads.**
The `main.py` docstring states *"No endpoint mutates the audit ledger"* — I need to establish
whether business rules are editable data or deployment-time reference data before designing any
edit affordance.

Reads required: `business_api/policy_view.py` (`5f725f46`), `persistence/models/policy.py`
(`030ff96f`), `persistence/models/reference.py` (`01b2a098`), `src/routes/policies.tsx`
(`e6bc1a21`), `src/routes/rules.tsx` (`44a50614`), and the `policy-service` surface on `:8104`.
