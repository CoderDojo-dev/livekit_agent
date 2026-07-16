"""knowledge-service entrypoint (Blueprint section 4.4 / 7.6): RAG search over the corpus.

`/health` is a real readiness probe, not a liveness lie: it proves the embedding model loads and
emits the configured width, and that the Qdrant collection exists with a matching dimension and
distance. If either is wrong the service reports 503 rather than answering callers from an index
it cannot actually search (RAG phase 2).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status

from knowledge_service.embeddings import EmbeddingError, get_embedder
from knowledge_service.qdrant_store import QdrantError, qdrant_collection, verify_collection
from knowledge_service.retriever import get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse
from service_auth import require_internal_key

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the ONNX session at boot.

    The first caller question should not be the one paying the model-load cost, and a broken
    image should fail visibly at startup instead of at the first call.
    """
    try:
        get_embedder().health_check()
        logger.info("embedding model warm and validated")
    except EmbeddingError as exc:
        logger.error("embedding model failed to warm up: %s", exc)
    yield


app = FastAPI(
    title="knowledge-service",
    dependencies=[Depends(require_internal_key)],
    lifespan=lifespan,
)
_retriever = get_retriever()


@app.get("/health")
def health(response: Response) -> dict:
    """Readiness: the embedding model and the vector collection must both be usable."""
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
    """Return ranked, source-attributed passages for a query."""
    passages = _retriever.search(req.query, top_k=req.top_k)
    return SearchResponse(
        passages=[PassageModel(text=p.text, source=p.source, score=p.score) for p in passages]
    )


def run() -> None:
    """Console-script entrypoint: `knowledge-service` (see [project.scripts]). Serves on :8102."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
