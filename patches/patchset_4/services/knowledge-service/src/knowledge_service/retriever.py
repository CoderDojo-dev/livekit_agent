"""Retrieval behind a small interface so the index implementation is swappable (KnowledgePort).

Phase 5 ships a dependency-free lexical retriever over the in-memory corpus. The production
swap is a Qdrant-backed embedding retriever implementing the same interface — the agent code
and MCP tool never change when it is replaced (Blueprint section 7.6 / ADR vector store).
"""
from __future__ import annotations

import logging
import os

import re
from dataclasses import dataclass

from knowledge_service.corpus import CORPUS, Document

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Passage:
    """A scored retrieval result carrying its citable source."""

    text: str
    source: str
    score: float


class LexicalRetriever:
    """Score documents by query-term overlap. Deterministic, no external dependency."""

    def __init__(self, documents: tuple[Document, ...] = CORPUS) -> None:
        self._documents = documents

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        """Return up to ``top_k`` passages whose text best matches ``query`` (score > 0)."""
        query_terms = set(_tokenize(query))
        if not query_terms:
            return []
        scored: list[Passage] = []
        for doc in self._documents:
            doc_terms = _tokenize(f"{doc.title} {doc.text}")
            overlap = sum(1 for term in doc_terms if term in query_terms)
            if overlap:
                score = overlap / (len(doc_terms) ** 0.5)
                scored.append(Passage(text=doc.text, source=doc.source, score=round(score, 4)))
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return scored[:top_k]


logger = logging.getLogger(__name__)


class QdrantRetriever:
    """Embedding retriever over Qdrant (report #6), same `search` interface as the lexical one."""

    def __init__(self, client, collection: str, embed) -> None:
        self._client = client
        self._collection = collection
        self._embed = embed

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        vector = self._embed(query)
        hits = self._client.search(collection_name=self._collection, query_vector=vector, limit=top_k)
        return [
            Passage(text=h.payload.get("text", ""), source=h.payload.get("source", ""), score=float(h.score))
            for h in hits
        ]


def _openai_embedder():
    """Return a callable str->vector using the OpenAI embeddings API (requires OPENAI_API_KEY)."""
    import httpx

    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(text: str) -> list[float]:
        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": text}, timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    return embed


def get_retriever():
    """Return the Qdrant retriever when QDRANT_URL is set and reachable; else the lexical one."""
    url = os.getenv("QDRANT_URL")
    if url:
        try:
            from qdrant_client import QdrantClient  # optional dependency

            collection = os.getenv("QDRANT_COLLECTION", "telecom_knowledge")
            return QdrantRetriever(QdrantClient(url=url), collection, _openai_embedder())
        except Exception as exc:  # noqa: BLE001
            logger.warning("qdrant unavailable (%s); falling back to lexical retriever", exc)
    return LexicalRetriever()
