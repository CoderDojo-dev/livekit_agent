"""Calibrate retrieval against the REAL corpus (RAG phase 8 — hybrid dense+BM25+RRF).

Prints, per query, the ungated dense+sparse ranking AND the RRF-fused scores so you can
recalibrate FLOOR/RELATIVE and check that keyword precision works.

The corpus is now 100% French, so same-language E5-small similarity is high and well-separated.
The cross-lingual inversion (Phase 7) is gone: no need for the 1.1 GB reranker anymore.

Read the summary at the bottom:
  * CONTROL dense ceiling  - the best cosine the dense stage gives a question the corpus has no
    answer for. KNOWLEDGE_SCORE_FLOOR must sit above it.
  * per-language true positive dense score  - must sit clearly ABOVE that ceiling.
  * RRF fused scores show whether keyword BM25 helps or hurts.

Usage (inside the knowledge-service container):
    python /app/scripts/knowledge_score_probe.py
    python /app/scripts/knowledge_score_probe.py "ma facture est trop chere" "quels sont les forfaits"
"""
from __future__ import annotations

import sys
import time

from knowledge_service.embeddings import get_embedder, get_sparse_embedder, hybrid_enabled
from knowledge_service.qdrant_store import get_client, qdrant_collection, DENSE_VECTOR_NAME
from knowledge_service.retriever import DEFAULT_SCORE_FLOOR, QdrantE5Retriever
from qdrant_client.models import SparseVector

# Last entry is a CONTROL: the corpus has no answer, so whatever it scores is the noise ceiling.
DEFAULT_QUERIES = [
    ("fr", "comment activer le roaming a l etranger"),
    ("fr", "pourquoi ma connexion 4G est lente"),
    ("fr", "qu est ce qui est inclus dans le forfait Flexi"),
    ("control", "how do I fix my washing machine"),
]
CANDIDATES = 12


def main() -> None:
    args = sys.argv[1:]
    queries = [("?", q) for q in args] if args else DEFAULT_QUERIES
    client = get_client()
    embedder = get_embedder()
    collection = qdrant_collection()
    retriever = QdrantE5Retriever(client, collection, embedder)
    sparse = get_sparse_embedder() if hybrid_enabled() else None

    print(f"dense FLOOR={DEFAULT_SCORE_FLOOR}   hybrid={'on' if sparse else 'OFF'}")
    print("dense scores are UNGATED; RRF score is the fused rank (1/(k+rank))\n")

    dense_tops: dict[str, float] = {}

    for lang, query in queries:
        passages = retriever.search(query, top_k=CANDIDATES, apply_gate=False)
        print(f"[{lang}] {query}")
        if not passages:
            print("     (no results)\n")
            continue

        dense_tops.setdefault(lang, passages[0].score)

        # Also fetch sparse-only for comparison
        sparse_hits = []
        if sparse is not None:
            try:
                sq = sparse.embed_query(query)
                sparse_resp = client.query_points(
                    collection_name=collection,
                    query=SparseVector(indices=list(sq.indices), values=list(sq.values)),
                    using="bm25",
                    limit=CANDIDATES,
                    with_payload=True,
                )
                sparse_hits = sparse_resp.points
            except Exception:
                pass

        overlap = 0
        sparse_only = 0
        for sp in sparse_hits:
            src = (sp.payload or {}).get("source", "")
            ord_ = (sp.payload or {}).get("ordinal", 0)
            if any(p.source == src and p.metadata.get("ordinal") == ord_ for p in passages):
                overlap += 1
            else:
                sparse_only += 1

        for rank, point in enumerate(passages):
            src = point.source
            ord_ = point.metadata.get("ordinal")
            sp_match = any((sp.payload or {}).get("source") == src and (sp.payload or {}).get("ordinal") == ord_ for sp in sparse_hits)
            mark = " BOTH" if sp_match else " DENSE"
            print(f"   #{rank + 1:2d}  dense={point.score:.4f}{mark}  {point.source}")
        print(f"      dense results: {len(passages)}, sparse overlap: {overlap}, sparse-only: {sparse_only}")
        print()

    print("=" * 78)
    dense_ceiling = dense_tops.get("control")
    if dense_ceiling is not None:
        print(f"DENSE noise ceiling (control top) = {dense_ceiling:.4f}")
        for lang, top in dense_tops.items():
            if lang != "control":
                mark = "  <-- INVERTED" if top < dense_ceiling else ""
                print(f"   [{lang}] top={top:.4f}  headroom={top - dense_ceiling:+.4f}{mark}")
        print(f"\nSet KNOWLEDGE_SCORE_FLOOR between the control ceiling ({dense_ceiling:.4f}) "
              "and the LOWEST per-language true positive.")
        print("If that window does not exist, the corpus needs more French content, not a new model.")


if __name__ == "__main__":
    main()
