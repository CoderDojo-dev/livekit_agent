"""knowledge-service entrypoint: grounded search and dependency readiness."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from qdrant_client import QdrantClient

from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.qdrant_store import QdrantConfig, verify_collection
from knowledge_service.retriever import get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse
from service_auth import require_internal_key

logger = logging.getLogger(__name__)
_nim_client: NIMEmbeddingClient | None = None
_qdrant_client: QdrantClient | None = None
_qdrant_config: QdrantConfig | None = None


def _get_nim_client() -> NIMEmbeddingClient:
    global _nim_client
    if _nim_client is None:
        _nim_client = NIMEmbeddingClient.from_env()
    return _nim_client


def _get_qdrant() -> tuple[QdrantClient, QdrantConfig]:
    global _qdrant_client, _qdrant_config
    if _qdrant_config is None:
        _qdrant_config = QdrantConfig.from_env()
    if _qdrant_client is None:
        _qdrant_client = _qdrant_config.client()
    return _qdrant_client, _qdrant_config


def _verify_dependencies() -> None:
    """Run blocking dependency probes off the event loop."""
    _get_nim_client().probe()
    client, config = _get_qdrant()
    verify_collection(client, config)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    if _nim_client is not None:
        _nim_client.close()
    if _qdrant_client is not None:
        _qdrant_client.close()


app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)
_retriever = get_retriever()


@app.get("/health")
async def health() -> dict[str, object]:
    """Readiness probe: fail unless NIM and the Qdrant collection are valid."""
    try:
        await run_in_threadpool(_verify_dependencies)
    except Exception as exc:
        logger.error("knowledge dependency readiness failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge dependencies are not ready",
        ) from exc

    _, config = _get_qdrant()
    return {
        "status": "ok",
        "checks": {"nvidia_nim": "ok", "qdrant_collection": "ok"},
        "collection": config.collection,
        "dimensions": config.dimensions,
    }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Return ranked, source-attributed passages."""
    passages = _retriever.search(req.query, top_k=req.top_k)
    return SearchResponse(
        passages=[PassageModel(text=p.text, source=p.source, score=p.score) for p in passages]
    )


def run() -> None:
    """Console-script entrypoint. Serves on port 8102."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
