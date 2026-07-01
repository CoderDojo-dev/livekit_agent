"""Retrieval behind a small interface so the index implementation is swappable (KnowledgePort).

Phase 5 ships a dependency-free lexical retriever over the in-memory corpus. The production
swap is a Qdrant-backed embedding retriever implementing the same interface — the agent code
and MCP tool never change when it is replaced (Blueprint section 7.6 / ADR vector store).
"""
from __future__ import annotations

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