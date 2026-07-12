"""knowledge-service entrypoint: strict dense retrieval and readiness."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from knowledge_service.retriever import QdrantNIMRetriever, get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse
from service_auth import require_internal_key

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Fail startup unless Qdrant and NVIDIA NIM are both usable."""
    retriever = await run_in_threadpool(get_retriever)
    app.state.retriever = retriever
    logger.info("strict Qdrant/NIM retriever is ready")
    try:
        yield
    finally:
        await run_in_threadpool(retriever.close)


app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)


def _retriever(request: Request) -> QdrantNIMRetriever:
    retriever = getattr(request.app.state, "retriever", None)
    if not isinstance(retriever, QdrantNIMRetriever):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dense retriever is not ready",
        )
    return retriever


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Report ready only after the strict dense retriever passed startup gates."""
    retriever = _retriever(request)
    return {
        "status": "ok",
        "retriever": "qdrant_nim",
        "checks": {"nvidia_nim": "ok", "qdrant_collection": "ok"},
        "collection": retriever.collection,
        "dimensions": retriever.embedder.config.dimensions,
    }


@app.post("/search", response_model=SearchResponse)
async def search(request: Request, req: SearchRequest) -> SearchResponse:
    """Embed a query with NIM and return Qdrant-ranked grounded passages."""
    retriever = _retriever(request)
    try:
        passages = await run_in_threadpool(retriever.search, req.query, req.top_k)
    except Exception as exc:
        logger.error("dense retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dense retrieval is unavailable",
        ) from exc

    return SearchResponse(
        passages=[
            PassageModel(
                text=passage.text,
                source=passage.source,
                score=passage.score,
                language=passage.language,
                document_type=passage.document_type,
                metadata=passage.metadata,
            )
            for passage in passages
        ]
    )


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
