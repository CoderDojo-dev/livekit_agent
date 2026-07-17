"""Calibrate the relevance gate against the REAL corpus (RAG phase 6b/6c).

Prints the TRUE ungated ranking from Qdrant (apply_gate=False). An earlier version passed
min_score=0.0 and called the result raw - it was not: min_score only zeroes the FLOOR, while the
RELATIVE cutoff kept filtering, so every passage below the ratio was invisible and the noise
looked smaller than it was. Calibrating from a gated sample is how you end up trusting a gate
that leaks.

How to read it:
  * CONTROL query - the corpus cannot answer it, so its TOP score is the noise ceiling.
    FLOOR must sit above that, with margin.
  * Every other query - the first big ratio drop is the boundary between "answers the question"
    and "merely telecom-shaped". RELATIVE goes just above the highest noise ratio you see.
  * Compare the top score per LANGUAGE. Cross-lingual scores run lower, so the headroom over the
    noise ceiling shrinks for fr/ar. If an Arabic true positive approaches FLOOR, the gate is
    about to start dropping real Arabic answers - that is the signal to move to a reranker or a
    larger e5 rather than to keep nudging thresholds.

Usage (inside the knowledge-service container):
    python /app/scripts/knowledge_score_probe.py
    python /app/scripts/knowledge_score_probe.py "ma facture est trop chere" "كيف أدفع فاتورتي"
"""
from __future__ import annotations

import sys

from knowledge_service.embeddings import get_embedder
from knowledge_service.qdrant_store import get_client, qdrant_collection
from knowledge_service.retriever import (
    DEFAULT_RELATIVE_CUTOFF,
    DEFAULT_SCORE_FLOOR,
    QdrantE5Retriever,
)

# Last entry is a CONTROL: the corpus has no answer, so whatever it scores is the noise ceiling.
DEFAULT_QUERIES = [
    ("en", "how do I activate roaming abroad"),
    ("fr", "comment activer le roaming a l etranger"),
    ("ar", "كيف أفعل التجوال الدولي"),
    ("en", "why is my mobile data slow"),
    ("en", "what is included in the Flexi plan"),
    ("control", "how do I fix my washing machine"),
]


def main() -> None:
    args = sys.argv[1:]
    queries = [("?", q) for q in args] if args else DEFAULT_QUERIES
    retriever = QdrantE5Retriever(get_client(), qdrant_collection(), get_embedder())

    print(f"gate: FLOOR={DEFAULT_SCORE_FLOOR}  RELATIVE={DEFAULT_RELATIVE_CUTOFF}")
    print("scores below are UNGATED (apply_gate=False) - the real ranking\n")

    tops: dict[str, float] = {}
    for lang, query in queries:
        passages = retriever.search(query, top_k=10, apply_gate=False)
        print(f"[{lang}] {query}")
        if not passages:
            print("     (no results)\n")
            continue
        top = passages[0].score
        tops.setdefault(lang, top)
        threshold = max(DEFAULT_SCORE_FLOOR, top * DEFAULT_RELATIVE_CUTOFF)
        for passage in passages:
            ratio = passage.score / top if top else 0.0
            verdict = "KEEP" if passage.score >= threshold else "drop"
            print(f"   {verdict}  {passage.score:.4f}  ratio={ratio:.3f}  {passage.source}")
        print()

    ceiling = tops.get("control")
    if ceiling is not None:
        print(f"noise ceiling (control top) = {ceiling:.4f}")
        print(f"FLOOR margin over noise     = {DEFAULT_SCORE_FLOOR - ceiling:+.4f}"
              "   (want clearly positive)")
        for lang, top in tops.items():
            if lang == "control":
                continue
            print(f"  [{lang}] top={top:.4f}  headroom over noise={top - ceiling:+.4f}"
                  f"  margin over FLOOR={top - DEFAULT_SCORE_FLOOR:+.4f}")
        print("\nIf a per-language 'margin over FLOOR' is near zero, real answers in that "
              "language are about to be dropped: raise the model, not the threshold.")


if __name__ == "__main__":
    main()
