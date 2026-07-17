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
from dataclasses import dataclass, field, replace

from knowledge_service.corpus import CORPUS, Document

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")

# --- Relevance gate -----------------------------------------------------------------------
# E5 is trained with a low-temperature (0.01) InfoNCE loss, so cosine scores compress into a
# narrow band: on this corpus a perfect hit scores 0.89 while two documents with NOTHING to do
# with the question still score 0.80 and 0.78. Returning them is not a ranking nuisance - it is
# a correctness problem. When the knowledge base has no answer, every passage is irrelevant yet
# still scores ~0.78, and an LLM handed three plausible-looking passages will ground an answer
# on them instead of saying it does not know.
#
# Two gates, because neither alone is safe:
#   * FLOOR    - an absolute cutoff. Kills the "nothing is relevant" case, where a relative
#                gate would happily keep the best of a bad set.
#   * RELATIVE - a share of the top score. Kills the "one good hit plus filler" case, and
#                adapts to the fact that E5's absolute scores drift between queries.
# A passage survives only if it clears BOTH.
#
# Calibrated on the 5-document corpus with scripts/knowledge_score_probe.py. Measured:
#
#   query                          top     noise kept @0.93        verdict
#   "activate roaming" (en)        0.8953  -                       clean
#   "activer le roaming" (fr)      0.8606  -                       clean
#   "التجوال الدولي" (ar)           0.8310  billing-cycle @0.965    LEAKED
#   "why is my data slow" (en)     0.8670  3 docs @0.944-0.964     LEAKED
#   "fix my washing machine"       0.7880  (control: all dropped)  clean
#
# RELATIVE 0.93 let ratios of 0.944-0.965 through, so it separated nothing; 0.97 drops every
# measured leak while keeping each true positive. Note this is a PRECISION choice: a second
# genuinely-relevant chunk scoring below 97% of the top is now dropped too. On a real corpus,
# where several chunks of one document are legitimately relevant and score close together, that
# is usually harmless - but re-run the probe before trusting it.
#
# LANGUAGE ASYMMETRY (structural, not a tuning artifact): cross-lingual similarity is
# systematically lower than same-language, so the headroom above the noise ceiling (0.7880) is
# en=0.107, fr=0.073, ar=0.043. One global FLOOR is therefore ~2.5x tighter for Arabic: it sits
# 0.012 above the control ceiling and only 0.031 below the true Arabic answer. That gap is the
# real limit of e5-small here, and no threshold can widen it - a cross-encoder reranker or a
# larger e5 can, at a RAM cost. Watch for Arabic false negatives first.
#
# SUPERSEDED BY PHASE 7. On the real 16-document corpus these thresholds are provably unusable:
# the control query peaks at 0.8411 while the Arabic true positive scores 0.8310 - the noise
# outranks the correct answer, so every FLOOR either admits the noise or deletes Arabic. They
# survive only as the degraded path when KNOWLEDGE_RERANKER_ENABLED=false, and remain calibrated
# for the 5-document corpus, not this one. The cross-encoder is the real gate now.
DEFAULT_SCORE_FLOOR = float(os.getenv("KNOWLEDGE_SCORE_FLOOR", "0.80"))
DEFAULT_RELATIVE_CUTOFF = float(os.getenv("KNOWLEDGE_RELATIVE_CUTOFF", "0.97"))


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
        apply_gate: bool = True,
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
        apply_gate: bool = True,
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
        # The reranker can only choose from what the bi-encoder returned, so over-fetch: a
        # correct passage the dense stage ranked 7th is invisible to a top_k=4 query.
        from knowledge_service.reranker import rerank_candidates, reranker_enabled

        use_reranker = apply_gate and reranker_enabled()
        limit = max(top_k, rerank_candidates()) if use_reranker else top_k
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=limit,
                with_payload=True,
                query_filter=self._build_filter(filters),
                score_threshold=min_score,
            )
        except Exception as exc:
            raise RetrieverUnavailable(f"qdrant search failed: {exc}") from exc

        passages = [self._passage(point) for point in response.points]
        if not apply_gate:
            # Calibration only: return what Qdrant ranked, ungated. `min_score=0` alone does NOT
            # do this - it zeroes the floor while the relative cutoff still filters, which made
            # an earlier probe report gated scores as if they were raw.
            return passages
        if use_reranker:
            return rerank_passages(query, passages, top_k)
        return apply_relevance_gate(passages, floor=min_score)[:top_k]


def rerank_passages(query: str, passages: list[Passage], top_k: int) -> list[Passage]:
    """Re-score dense candidates with the cross-encoder and keep only the relevant ones.

    The returned `score` becomes the cross-encoder relevance probability (0-1); the original
    cosine lands in `metadata["dense_score"]` so the two stages stay comparable in the probe.

    On reranker failure this raises rather than falling back to the cosine gate. That gate is
    measurably broken on this corpus - the control query sails through it - so falling back
    would feed the agent confident noise. An honest 503 makes the agent say it has no
    information; a silent downgrade makes it invent one.
    """
    from knowledge_service.reranker import RerankError, get_reranker, rerank_threshold

    if not passages:
        return []
    try:
        scores = get_reranker().score(query, [passage.text for passage in passages])
    except RerankError as exc:
        raise RetrieverUnavailable(f"reranker unavailable: {exc}") from exc

    threshold = rerank_threshold()
    ranked = sorted(zip(passages, scores), key=lambda pair: pair[1], reverse=True)
    kept = [
        replace(
            passage,
            score=round(score, 4),
            metadata={**passage.metadata, "dense_score": passage.score},
        )
        for passage, score in ranked
        if score >= threshold
    ]
    if len(kept) < len(passages):
        logger.info(
            "reranker: kept %d/%d passages (threshold=%.2f, best=%.4f)",
            len(kept), len(passages), threshold, ranked[0][1] if ranked else 0.0,
        )
    return kept[:top_k]


def apply_relevance_gate(
    passages: list[Passage],
    floor: float | None = None,
    relative: float | None = None,
) -> list[Passage]:
    """Drop passages that are merely the *least bad* rather than actually relevant.

    Pure and order-preserving (Qdrant already returns best-first). Returning an empty list is a
    valid, desirable answer: it makes the agent say it has no information instead of inventing
    one from filler.
    """
    if not passages:
        return []
    floor = DEFAULT_SCORE_FLOOR if floor is None else floor
    relative = DEFAULT_RELATIVE_CUTOFF if relative is None else relative

    top = max(passage.score for passage in passages)
    threshold = max(floor, top * relative)
    kept = [passage for passage in passages if passage.score >= threshold]
    if len(kept) < len(passages):
        logger.info(
            "relevance gate: kept %d/%d passages (top=%.4f, threshold=%.4f)",
            len(kept), len(passages), top, threshold,
        )
    return kept


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
