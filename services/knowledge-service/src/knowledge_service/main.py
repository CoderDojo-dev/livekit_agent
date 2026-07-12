"""knowledge-service entrypoint: production-gated hybrid retrieval."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from persistence.engine import get_sessionmaker

from knowledge_service.qdrant_store import QdrantConfig
from knowledge_service.readiness import ReadinessReport, verify_production_readiness
from knowledge_service.retriever import HybridRetriever, SearchFilters, get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse
from service_auth import require_internal_key

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    retriever = await run_in_threadpool(get_retriever)
    try:
        report = await run_in_threadpool(
            verify_production_readiness,
            qdrant=retriever.dense.client,
            qdrant_config=QdrantConfig.from_env(),
            embedder=retriever.embedder,
            session_factory=get_sessionmaker(),
        )
    except Exception:
        await run_in_threadpool(retriever.close)
        raise
    app.state.retriever = retriever
    app.state.readiness = report
    logger.info(
        "production RAG ready: qdrant_points=%s postgres_chunks=%s",
        report.qdrant_points,
        report.postgres_active_chunks,
    )
    try:
        yield
    finally:
        await run_in_threadpool(retriever.close)


app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)


def _retriever(request: Request) -> HybridRetriever:
    retriever = getattr(request.app.state, "retriever", None)
    if not isinstance(retriever, HybridRetriever):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production RAG is not ready",
        )
    return retriever


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    retriever = _retriever(request)
    report = getattr(request.app.state, "readiness", None)
    if not isinstance(report, ReadinessReport):
        raise HTTPException(status_code=503, detail="readiness report is unavailable")
    return {
        "status": "ok",
        "retriever": "qdrant_nim_postgres_rrf",
        "checks": {
            "nvidia_nim": "ok",
            "qdrant_collection": "ok",
            "qdrant_nonempty": "ok",
            "postgres_fts": "ok",
            "postgres_nonempty": "ok",
            "no_lexical_fallback": "ok",
        },
        "collection": retriever.collection,
        "dimensions": report.dimensions,
        "qdrant_points": report.qdrant_points,
        "postgres_active_chunks": report.postgres_active_chunks,
    }


@app.post("/search", response_model=SearchResponse)
async def search(request: Request, req: SearchRequest) -> SearchResponse:
    retriever = _retriever(request)
    filters = SearchFilters(
        language=req.language,
        document_type=req.document_type,
        applicable_plans=tuple(req.applicable_plans),
    )
    try:
        passages = await run_in_threadpool(
            retriever.search,
            req.query,
            req.top_k,
            filters,
        )
    except Exception as exc:
        logger.error("hybrid retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="hybrid retrieval is unavailable",
        ) from exc
    return SearchResponse(
        passages=[
            PassageModel(
                text=item.text,
                source=item.source,
                score=item.score,
                language=item.language,
                document_type=item.document_type,
                metadata=item.metadata,
            )
            for item in passages
        ]
    )


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
