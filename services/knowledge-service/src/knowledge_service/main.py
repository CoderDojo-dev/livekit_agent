"""knowledge-service entrypoint (Blueprint section 4.4 / 7.6): RAG search over the corpus.

`/health` is a real readiness probe, not a liveness lie: it proves the embedding model loads and
emits the configured width, and that the Qdrant collection exists with a matching dimension and
distance. If either is wrong the service reports 503 rather than answering callers from an index
it cannot actually search (RAG phase 2).

`/search` is dense-only (RAG phase 4). When the index is unusable it returns 503 instead of
quietly serving term-overlap results that look like RAG but are not.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from knowledge_service.embeddings import EmbeddingError, get_embedder
from knowledge_service.qdrant_store import QdrantError, qdrant_collection, verify_collection
from knowledge_service.retriever import RetrieverUnavailable, get_retriever
from knowledge_service.schemas import (
    DocumentListResponse,
    DocumentSummary,
    PassageModel,
    PurgeResponse,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)
from service_auth import require_internal_key

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the ONNX session and the retriever at boot.

    The first caller question should not pay the model-load cost, and a broken index should be
    visible in the logs at startup. Failures are logged, not raised: the container stays up and
    reports 503 on /health and /search, which is easier to diagnose than a crash-loop.
    """
    try:
        get_embedder().health_check()
        logger.info("embedding model warm and validated")
    except EmbeddingError as exc:
        logger.error("embedding model failed to warm up: %s", exc)
    try:
        get_retriever()
        logger.info("dense retriever ready")
    except RetrieverUnavailable as exc:
        logger.error("retriever unavailable: %s", exc)
    from knowledge_service.reranker import RerankError, get_reranker, reranker_enabled

    if reranker_enabled():
        try:
            get_reranker().health_check()  # ~1.1 GB: not on the first caller's question
            logger.info("reranker warm and validated")
        except RerankError as exc:
            logger.error("reranker failed to warm up: %s", exc)
    yield


app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)


@app.get("/health")
def health(response: Response) -> dict:
    """Readiness: the embedding model, the collection, and the retriever must all be usable."""
    checks: dict[str, str] = {}
    embedder = get_embedder()

    try:
        embedder.health_check()
        checks["embedder"] = "ok"
    except EmbeddingError as exc:
        checks["embedder"] = f"error: {exc}"

    points: int | None = None
    try:
        report = verify_collection()
        points = report["points"]
        checks["qdrant_collection"] = "ok"
    except QdrantError as exc:
        checks["qdrant_collection"] = f"error: {exc}"

    try:
        get_retriever()
        checks["retriever"] = "ok"
    except RetrieverUnavailable as exc:
        checks["retriever"] = f"error: {exc}"

    # The reranker IS the relevance gate on this corpus; if it is dead /search returns 503, so
    # readiness must reflect it instead of reporting a healthy-but-mute service.
    from knowledge_service.reranker import RerankError, get_reranker, reranker_enabled

    if reranker_enabled():
        try:
            get_reranker().health_check()
            checks["reranker"] = "ok"
        except RerankError as exc:
            checks["reranker"] = f"error: {exc}"

    ready = all(value == "ok" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if ready else "degraded",
        "model": embedder.model_name,
        "dimensions": embedder.dimensions,
        "collection": qdrant_collection(),
        "points": points,
        "checks": checks,
    }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Return ranked, source-attributed passages for a query. 503 when the index is unusable."""
    try:
        passages = get_retriever().search(
            req.query, top_k=req.top_k, filters=req.filters(), min_score=req.min_score
        )
    except RetrieverUnavailable as exc:
        # Never fall back to term overlap: a plausible wrong answer is worse than a clear failure.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return SearchResponse(
        passages=[
            PassageModel(
                text=p.text, source=p.source, score=p.score, title=p.title,
                language=p.language, document_type=p.document_type,
                version=p.version, metadata=p.metadata,
            )
            for p in passages
        ]
    )


@app.post("/knowledge/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("general"),
    auto_ingest: bool = Form(True),
) -> UploadResponse:
    """Store a document in the knowledge bucket and index it immediately.

    `document_type` becomes the bucket folder and the retrievable taxonomy, so an operator can
    add a PDF/DOCX/CSV/JSON/Markdown file and have it searchable when the call returns - without
    the two manual CLI steps that previously blocked iterative testing.

    Ingestion runs in a worker thread: parsing and embedding are CPU-bound and would otherwise
    stall the event loop serving live `/search` traffic.
    """
    from knowledge_service.ingestion import store_and_ingest

    raw = await file.read()
    try:
        result = await run_in_threadpool(
            store_and_ingest, raw, file.filename or "", document_type, auto_ingest
        )
    except ValueError as exc:  # rejected input: unsupported format, empty, too large
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:  # storage/pipeline problem: surfaced, never a silent no-op
        logger.exception("upload failed for %s", file.filename)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if result["status"] == "failed":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result["message"])
    return UploadResponse(**result)


@app.get("/knowledge/documents", response_model=DocumentListResponse)
async def list_knowledge_documents() -> DocumentListResponse:
    """Inventory of the corpus: what is indexed, in what version, with how many live chunks.

    Without this an operator cannot see what the agent will answer from - and cannot spot that a
    stray upload is outranking real procedures.
    """
    from knowledge_service.lifecycle import list_documents
    from persistence.engine import session_scope

    def _read() -> list[dict]:
        with session_scope() as session:
            return list_documents(session)

    rows = await run_in_threadpool(_read)
    documents = [DocumentSummary(**row) for row in rows]
    return DocumentListResponse(
        documents=documents,
        total_documents=len(documents),
        total_chunks=sum(document.chunks for document in documents),
    )


@app.delete("/knowledge/documents/{source:path}", response_model=PurgeResponse)
async def purge_knowledge_document(source: str, remove_object: bool = True) -> PurgeResponse:
    """Remove a document from the index, the records, and the bucket.

    `source` is the bucket key (e.g. `tests/env_config.txt`), so it contains slashes - hence the
    `:path` converter. The object is deleted by default: an archived document no longer matches
    the checksum guard, so a file left in the bucket would be re-ingested on the next scan.
    """
    from knowledge_service.lifecycle import purge_document
    from knowledge_service.retriever import reset_retriever
    from persistence.engine import session_scope

    def _purge() -> dict:
        with session_scope() as session:
            return purge_document(session, source, remove_object=remove_object)

    try:
        result = await run_in_threadpool(_purge)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("purge failed for %s", source)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    reset_retriever()  # the index shrank; drop any memo (it may now be empty)
    return PurgeResponse(**result)


def run() -> None:
    """Console-script entrypoint: `knowledge-service` (see [project.scripts]). Serves on :8102."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
