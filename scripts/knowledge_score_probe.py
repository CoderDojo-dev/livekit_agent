"""Calibrate retrieval against the REAL corpus (RAG phase 7).

Prints, per query, the ungated dense ranking AND the cross-encoder score for the same passages,
so the two stages can be compared on identical candidates.

Why both: on the 16-document corpus the dense stage inverted - the control query ("how do I fix
my washing machine") peaked at 0.8411 while the Arabic true positive scored 0.8310, so the noise
outranked the correct answer and no FLOOR could separate them. The question this probe answers
is whether the cross-encoder pulls those apart.

Read the summary at the bottom:
  * CONTROL rerank ceiling  - the best relevance the reranker gives a question the corpus cannot
    answer. KNOWLEDGE_RERANK_THRESHOLD must sit above it.
  * per-language true positive rerank score - must sit clearly ABOVE that ceiling, in every
    language. If Arabic still lands under the control, the reranker has not fixed the inversion
    either, and the corpus needs Arabic content rather than another model.

Usage (inside the knowledge-service container):
    python /app/scripts/knowledge_score_probe.py
    python /app/scripts/knowledge_score_probe.py "ma facture est trop chere" "كيف أدفع فاتورتي"
"""
from __future__ import annotations

import sys
import time

from knowledge_service.embeddings import get_embedder
from knowledge_service.qdrant_store import get_client, qdrant_collection
from knowledge_service.retriever import DEFAULT_SCORE_FLOOR, QdrantE5Retriever
from knowledge_service.reranker import get_reranker, rerank_threshold, reranker_enabled

# Last entry is a CONTROL: the corpus has no answer, so whatever it scores is the noise ceiling.
DEFAULT_QUERIES = [
    ("en", "how do I activate roaming abroad"),
    ("fr", "comment activer le roaming a l etranger"),
    ("ar", "كيف أفعل التجوال الدولي"),
    ("en", "why is my mobile data slow"),
    ("en", "what is included in the Flexi plan"),
    ("control", "how do I fix my washing machine"),
]
CANDIDATES = 10


def main() -> None:
    args = sys.argv[1:]
    queries = [("?", q) for q in args] if args else DEFAULT_QUERIES
    retriever = QdrantE5Retriever(get_client(), qdrant_collection(), get_embedder())
    use_reranker = reranker_enabled()
    reranker = get_reranker() if use_reranker else None
    threshold = rerank_threshold()

    print(f"dense FLOOR (legacy)={DEFAULT_SCORE_FLOOR}   reranker={'on' if use_reranker else 'OFF'}"
          f"   RERANK_THRESHOLD={threshold}")
    print("dense scores are UNGATED; rerank column is the cross-encoder relevance (0-1)\n")

    dense_tops: dict[str, float] = {}
    rerank_tops: dict[str, float] = {}

    for lang, query in queries:
        passages = retriever.search(query, top_k=CANDIDATES, apply_gate=False)
        print(f"[{lang}] {query}")
        if not passages:
            print("     (no results)\n")
            continue

        scores = [0.0] * len(passages)
        elapsed = 0.0
        if reranker is not None:
            start = time.time()
            scores = reranker.score(query, [passage.text for passage in passages])
            elapsed = (time.time() - start) * 1000

        dense_tops.setdefault(lang, passages[0].score)
        order = sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)
        if reranker is not None:
            rerank_tops.setdefault(lang, scores[order[0]])

        for rank, index in enumerate(order):
            passage, score = passages[index], scores[index]
            verdict = "KEEP" if (reranker is None or score >= threshold) else "drop"
            print(f"   {verdict}  rerank={score:.4f}  dense={passage.score:.4f}  "
                  f"(dense#{index + 1})  {passage.source}")
        if reranker is not None:
            print(f"      reranked {len(passages)} candidates in {elapsed:.0f}ms")
        print()

    print("=" * 78)
    dense_ceiling = dense_tops.get("control")
    if dense_ceiling is not None:
        print(f"DENSE  noise ceiling (control top) = {dense_ceiling:.4f}")
        for lang, top in dense_tops.items():
            if lang != "control":
                mark = "  <-- INVERTED" if top < dense_ceiling else ""
                print(f"   [{lang}] top={top:.4f}  headroom={top - dense_ceiling:+.4f}{mark}")
    rerank_ceiling = rerank_tops.get("control")
    if rerank_ceiling is not None:
        print(f"\nRERANK noise ceiling (control top) = {rerank_ceiling:.4f}"
              f"   threshold={threshold}")
        for lang, top in rerank_tops.items():
            if lang != "control":
                mark = "  <-- STILL INVERTED" if top < rerank_ceiling else ""
                print(f"   [{lang}] top={top:.4f}  headroom={top - rerank_ceiling:+.4f}{mark}")
        print("\nSet KNOWLEDGE_RERANK_THRESHOLD between the control ceiling and the LOWEST "
              "per-language true positive.")
        print("If that window does not exist, the reranker has not separated them either: the "
              "corpus is the problem, not the model.")


if __name__ == "__main__":
    main()
