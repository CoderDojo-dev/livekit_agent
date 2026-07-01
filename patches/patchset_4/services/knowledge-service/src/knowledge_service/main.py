"""knowledge-service entrypoint (Blueprint section 4.4 / 7.6): RAG search over the corpus."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi import Depends
from service_auth import require_internal_key

from knowledge_service.retriever import get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse

app = FastAPI(title="knowledge-service", dependencies=[Depends(require_internal_key)])
_retriever = get_retriever()


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Return ranked, source-attributed passages for an English query."""
    passages = _retriever.search(req.query, top_k=req.top_k)
    return SearchResponse(
        passages=[PassageModel(text=p.text, source=p.source, score=p.score) for p in passages]
    )