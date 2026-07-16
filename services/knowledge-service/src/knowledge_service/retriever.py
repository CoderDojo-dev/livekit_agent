"""Retrieval behind a small interface so the index implementation is swappable (KnowledgePort).

RAG phase 4 makes dense retrieval the ONLY production path. The previous factory silently fell
back to the lexical retriever whenever the vector path raised - and it always raised here,
because it required OPENAI_API_KEY, which this platform does not use. The agent therefore
answered from term-overlap over an in-memory corpus while appearing to be RAG-backed. A silent
downgrade is worse than an outage: nobody sees it, and the answers look plausible.

Now: if the collection or the embedding model is unusable, retrieval reports the failure and the
service refuses to answer. LexicalRetriever survives only for offline unit tests.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from knowledge_service.corpus import CORPUS, Document

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Passage:
    """A scored retrieval result carrying everything needed to cite it out loud."""

    text: str
    source: str
    score: float
    title: str = ""
    language: str = ""
    document_type: str = ""
    version: int = 0
    metadata: dict = field(default_factory=dict)


class RetrieverUnavailable(RuntimeError):
    """The vector index cannot serve queries. Surfaced, never swallowed into a fallback."""


class LexicalRetriever:
    """Term-overlap scoring over the in-memory corpus.

    OFFLINE TESTS ONLY. Not reachable in production: `get_retriever` never returns it unless
    KNOWLEDGE_ALLOW_LEXICAL_FALLBACK is explicitly set, which exists so a developer can opt in
    deliberately - not so the system can degrade behind your back.
    """

    def __init__(self, documents: tuple[Document, ...] = CORPUS) -> None:
        self._documents = documents

    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> list[Passage]:
        """Return up to ``top_k`` passages whose text best matches ``query`` (score > 0).

        Accepts (and ignores) filters so it stays signature-compatible with the dense retriever.
        """
        query_terms = set(_tokenize(query))
        if not query_terms:
            return []
        scored: list[Passage] = []
        for doc in self._documents:
            doc_terms = _tokenize(f"{doc.title} {doc.text}")
            overlap = sum(1 for term in doc_terms if term in query_terms)
            if overlap:
                score = overlap / (len(doc_terms) ** 0.5)
                scored.append(
                    Passage(
                        text=doc.text, source=doc.source, score=round(score, 4),
                        title=doc.title, language="en", document_type="corpus",
                    )
                )
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return scored[:top_k]


class QdrantE5Retriever:
    """Dense retriever: embed the question as a `query:`, search Qdrant, return cited passages.

    Only ACTIVE chunks are searched (payload-indexed filter), so a superseded revision of a
    procedure can never be quoted to a caller after the document is re-ingested.
    """

    def __init__(self, client, collection: str, embedder) -> None:
        self._client = client
        self._collection = collection
        self._embedder = embedder

    @staticmethod
    def _passage(point) -> Passage:
        payload = point.payload or {}
        return Passage(
            text=payload.get("text", ""),
            source=payload.get("source", ""),
            score=round(float(point.score), 4),
            title=payload.get("title", ""),
            language=payload.get("language", ""),
            document_type=payload.get("document_type", ""),
            version=int(payload.get("version") or 0),
            metadata={
                "document_id": payload.get("document_id", ""),
                "ordinal": payload.get("ordinal", 0),
                "checksum": payload.get("checksum", ""),
                "applicable_plans": payload.get("applicable_plans", []),
                "product_codes": payload.get("product_codes", []),
                "region": payload.get("region", ""),
                "valid_from": payload.get("valid_from", ""),
                "valid_until": payload.get("valid_until", ""),
            },
        )

    @staticmethod
    def _build_filter(filters: dict | None):
        """Translate caller filters into a Qdrant pre-filter.

        `active` is always enforced so a superseded revision can never be quoted. List-valued
        payloads (applicable_plans, product_codes) use MatchAny: a passage matches if ANY of its
        values is requested, which is the right semantics for "does this apply to my plan?".
        """
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        must = [FieldCondition(key="active", match=MatchValue(value=True))]
        filters = filters or {}
        for field in ("language", "document_type", "region"):
            value = filters.get(field)
            if value:
                must.append(FieldCondition(key=field, match=MatchValue(value=str(value))))
        for field in ("applicable_plans", "product_codes"):
            values = filters.get(field)
            if values:
                must.append(
                    FieldCondition(key=field, match=MatchAny(any=[str(v) for v in values]))
                )
        return Filter(must=must)

    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> list[Passage]:
        """Return the ``top_k`` nearest active passages matching ``filters``.

        ``min_score`` is passed to Qdrant as a cutoff. Calibrate it for E5: its low-temperature
        (0.01) InfoNCE training makes cosine scores cluster around 0.7-1.0, so a 0.5 threshold
        borrowed from another model filters nothing, and 0.9 filters everything.
        """
        if not query or not query.strip():
            return []
        try:
            vector = self._embedder.embed_query(query)  # applies the `query: ` prefix
        except Exception as exc:
            raise RetrieverUnavailable(f"cannot embed query: {exc}") from exc
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=top_k,
                with_payload=True,
                query_filter=self._build_filter(filters),
                score_threshold=min_score,
            )
        except Exception as exc:
            raise RetrieverUnavailable(f"qdrant search failed: {exc}") from exc
        return [self._passage(point) for point in response.points]


_retriever = None


def build_retriever():
    """Construct the production retriever, verifying the index first. Raises on any problem."""
    if os.getenv("KNOWLEDGE_ALLOW_LEXICAL_FALLBACK", "").lower() == "true":
        logger.warning(
            "KNOWLEDGE_ALLOW_LEXICAL_FALLBACK is set: serving TERM-OVERLAP results, not vectors. "
            "This is a development escape hatch and must never be set in production."
        )
        return LexicalRetriever()

    from knowledge_service.embeddings import get_embedder
    from knowledge_service.qdrant_store import QdrantError, get_client, qdrant_collection, verify_collection

    try:
        client = get_client()
        report = verify_collection(client=client)
    except QdrantError as exc:
        raise RetrieverUnavailable(str(exc)) from exc

    if report["points"] == 0:
        # An empty index answers every question with silence. That is a configuration error
        # (nothing ingested, or the outbox never drained), not a valid state to serve from.
        raise RetrieverUnavailable(
            f"collection {report['collection']!r} is empty: ingest the corpus "
            f"(`knowledge-ingest`) and drain the outbox (`knowledge-sync-outbox`)"
        )

    return QdrantE5Retriever(client, qdrant_collection(), get_embedder())


def get_retriever():
    """Process-wide retriever, built lazily so a cold Qdrant does not crash-loop the container."""
    global _retriever
    if _retriever is None:
        _retriever = build_retriever()
    return _retriever


def reset_retriever() -> None:
    """Drop the memoized retriever (used after the index changes)."""
    global _retriever
    _retriever = None
