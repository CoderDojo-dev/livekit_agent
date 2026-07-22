"""Calibrate the 3-layer gate against the REAL corpus (RAG phase 8.1).

P0 FIX: ce_top1 (ungated dense top-1) is NOT the gate's decision variable. The gate
CE-scores the RRF-fused survivors, which are a DIFFERENT set of passages. This probe now
prints BOTH so the decoupling is visible, plus ce_max_kept (the actual decision variable)
computed by replicating the gated pipeline's intermediate state.

Columns:
  | query | type | dense_top1 | max_bm25 | ce_top1 | ce_max_kept | fused_n | gated_verdict | expected | PASS? |

  - dense_top1:  raw dense cosine of the ungated top-1 (calibrates FLOOR)
  - max_bm25:    max BM25 among ungated sparse hits (calibrates SPARSE_MIN)
  - ce_top1:     CE score of the ungated dense top-1 (OLD column — NOT the gate's input)
  - ce_max_kept: CE score of the ACTUAL gated survivors (RRF-fused, the gate's decision variable)
  - fused_n:     how many passages the CE gate actually evaluated (diagnoses P1 displacement)
  - gated_verdict: RETURN(n) or EMPTY from the real gated search

Usage (inside the knowledge-service container):
    python /app/scripts/knowledge_score_probe.py
"""
from __future__ import annotations

import sys

from knowledge_service.embeddings import get_embedder, get_sparse_embedder, hybrid_enabled
from knowledge_service.qdrant_store import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    get_client,
    qdrant_collection,
)
from knowledge_service.retriever import (
    DEFAULT_LANGUAGE_FILTER,
    DEFAULT_SCORE_FLOOR,
    SPARSE_MIN,
    QdrantE5Retriever,
)
from qdrant_client.models import SparseVector

DEFAULT_QUERIES: list[tuple[str, str]] = [
    ("comment activer le roaming international", "tp"),
    ("ma facture est trop elevee ce mois-ci", "tp"),
    ("combien coute le forfait Flexi a 25 TND", "tp"),
    ("c est quoi les options data boost nuit weekend", "tp"),
    ("mon internet 4G ne marche plus", "tp"),
    ("comment changer de forfait mobile", "tp"),
    ("je n ai plus de signal depuis mon arrivee", "tp"),
    ("quels sont les forfaits internet fixes", "tp"),
    ("transferer mon numero vers Tunisie Telecom", "tp"),
    ("code USSD pour consulter mon solde", "tp"),
    ("delai de retractation droit de renoncer", "noise"),
    ("est ce que lesim est disponible", "noise"),
    ("service apres vente telephone", "noise"),
    ("reparation machine a laver", "noise"),
    ("meteo tunis aujourd hui", "noise"),
    ("recrutement Tunisie Telecom", "noise"),
    ("horaires ouverture agence", "noise"),
    ("how do I fix my washing machine", "noise"),
]
CANDIDATES = 12


def main() -> None:
    args = sys.argv[1:]
    queries: list[tuple[str, str]] = []
    if args:
        for q in args:
            queries.append((q, "?"))
    else:
        queries = list(DEFAULT_QUERIES)

    client = get_client()
    embedder = get_embedder()
    collection = qdrant_collection()
    retriever = QdrantE5Retriever(client, collection, embedder)
    sparse = get_sparse_embedder() if hybrid_enabled() else None

    ce_gate = None
    ce_on = False
    try:
        from knowledge_service.ce_gate import ce_gate_enabled, ce_max_candidates, get_ce_gate

        ce_on = ce_gate_enabled()
        if ce_on:
            ce_gate = get_ce_gate()
    except Exception:
        pass

    rows: list[dict] = []

    for query, qtype in queries:
        dense_top1 = 0.0
        max_bm25 = 0.0
        ce_top1 = 0.0
        ce_max_kept = 0.0
        fused_n = 0

        # --- Ungated pass: raw dense + bm25 + old ce_top1 (for comparison) ---
        ungated = retriever.search(query, top_k=CANDIDATES, apply_gate=False)
        if ungated:
            dense_top1 = round(ungated[0].score, 4)

        if sparse is not None:
            try:
                sq = sparse.embed_query(query)
                resp = client.query_points(
                    collection_name=collection,
                    query=SparseVector(indices=list(sq.indices), values=list(sq.values)),
                    using=SPARSE_VECTOR_NAME,
                    limit=CANDIDATES,
                    with_payload=True,
                )
                if resp.points:
                    max_bm25 = round(float(resp.points[0].score), 4)
            except Exception:
                pass

        if ce_gate is not None and ungated:
            try:
                from knowledge_service.ce_gate import ce_max_candidates

                candidates = ungated[:ce_max_candidates()]
                scores = ce_gate.scores(query, [p.text for p in candidates])
                if scores:
                    ce_top1 = round(max(scores), 4)
            except Exception:
                pass

        # --- Gated pipeline replication: measure the ACTUAL decision variable (P0 fix) ---
        # The gate does: dense search (score_threshold=floor) → sparse → RRF fuse to
        # ce_max_candidates width → CE-score the fused list. We replicate that here so
        # ce_max_kept is the max CE score among the SAME passages the gate evaluates.
        if ce_on and ce_gate is not None:
            try:
                from knowledge_service.ce_gate import ce_max_candidates

                qfilter = QdrantE5Retriever._build_filter({"language": DEFAULT_LANGUAGE_FILTER})
                dense_vec = embedder.embed_query(query)

                # Gated dense search (with score_threshold = FLOOR)
                gated_dense = client.query_points(
                    collection_name=collection,
                    query=dense_vec,
                    using=DENSE_VECTOR_NAME,
                    limit=CANDIDATES,
                    with_payload=True,
                    query_filter=qfilter,
                    score_threshold=DEFAULT_SCORE_FLOOR,
                ).points

                if gated_dense and sparse is not None:
                    # Sparse search
                    sq = sparse.embed_query(query)
                    gated_sparse = client.query_points(
                        collection_name=collection,
                        query=SparseVector(indices=list(sq.indices), values=list(sq.values)),
                        using=SPARSE_VECTOR_NAME,
                        limit=CANDIDATES,
                        with_payload=True,
                        query_filter=qfilter,
                    ).points

                    # RRF fuse to ce_max_candidates width (same as the gate)
                    fuse_width = ce_max_candidates()
                    fused = QdrantE5Retriever._rrf_fuse(gated_dense, gated_sparse, fuse_width)
                    fused_n = len(fused)

                    # CE-score the ACTUAL fused survivors
                    if fused:
                        ce_scores = ce_gate.scores(query, [p.text for p in fused])
                        if ce_scores:
                            ce_max_kept = round(max(ce_scores), 4)
            except Exception:
                # Don't crash the probe; report 0 so the row is still printed
                pass

        # --- Gated pass: production verdict ---
        gated = retriever.search(query, top_k=4, apply_gate=True)
        gated_verdict = f"RETURN({len(gated)})" if gated else "EMPTY"

        expected = qtype
        passed = (gated_verdict != "EMPTY" and qtype == "tp") or (gated_verdict == "EMPTY" and qtype == "noise")
        pass_mark = "✓" if passed else "✗"

        rows.append({
            "query": query,
            "type": qtype,
            "dense_top1": dense_top1,
            "max_bm25": max_bm25,
            "ce_top1": ce_top1,
            "ce_max_kept": ce_max_kept,
            "fused_n": fused_n,
            "gated_verdict": gated_verdict,
            "expected": expected,
            "pass": pass_mark,
        })

    # --- Markdown table ---
    header = "| query | type | dense_top1 | max_bm25 | ce_top1 | ce_max_kept | fused_n | gated_verdict | expected | PASS? |"
    sep = "|-------|------|-----------:|---------:|--------:|------------:|--------:|---------------|----------|-------|"
    print(f"FLOOR={DEFAULT_SCORE_FLOOR}  SPARSE_MIN={SPARSE_MIN}  hybrid={'on' if sparse else 'OFF'}  CE={'on' if ce_gate else 'OFF'}")
    print()
    print(header)
    print(sep)
    for r in rows:
        print(
            f"| {r['query']} | {r['type']} | {r['dense_top1']:.4f} | {r['max_bm25']:.4f} "
            f"| {r['ce_top1']:.4f} | {r['ce_max_kept']:.4f} | {r['fused_n']} "
            f"| {r['gated_verdict']} | {r['expected']} | {r['pass']} |"
        )
    print()

    # --- Summary: calibration windows on the ACTUAL decision variable ---
    tp_rows = [r for r in rows if r["type"] == "tp"]
    noise_rows = [r for r in rows if r["type"] == "noise"]

    if tp_rows:
        lt = min(tp_rows, key=lambda r: r["dense_top1"])
        lb = min(tp_rows, key=lambda r: r["max_bm25"])
        lc = min(tp_rows, key=lambda r: r["ce_max_kept"])
        print(
            f"lowest TP:  dense={lt['dense_top1']:.4f} ({lt['query']})  "
            f"bm25={lb['max_bm25']:.4f} ({lb['query']})  "
            f"ce_max_kept={lc['ce_max_kept']:.4f} ({lc['query']})"
        )
    if noise_rows:
        ht = max(noise_rows, key=lambda r: r["dense_top1"])
        hb = max(noise_rows, key=lambda r: r["max_bm25"])
        hc = max(noise_rows, key=lambda r: r["ce_max_kept"])
        print(
            f"highest noise: dense={ht['dense_top1']:.4f} ({ht['query']})  "
            f"bm25={hb['max_bm25']:.4f} ({hb['query']})  "
            f"ce_max_kept={hc['ce_max_kept']:.4f} ({hc['query']})"
        )
    print()

    # --- P0 diagnostic: show the decoupling (ce_top1 vs ce_max_kept) ---
    print("P0 diagnostic (ce_top1 = ungated dense top-1, ce_max_kept = actual gated survivors):")
    for r in rows:
        if abs(r["ce_top1"] - r["ce_max_kept"]) > 0.01:
            print(
                f"  {r['query'][:50]:50s}  ce_top1={r['ce_top1']:.4f}  "
                f"ce_max_kept={r['ce_max_kept']:.4f}  delta={r['ce_max_kept'] - r['ce_top1']:+.4f}"
            )
    print()

    print("Calibration (use ce_max_kept, NOT ce_top1):")
    print("  Set KNOWLEDGE_CE_THRESHOLD between the lowest TP ce_max_kept and the highest noise ce_max_kept.")
    print("  Set KNOWLEDGE_SPARSE_MIN between the lowest TP max_bm25 and the highest noise max_bm25.")
    print("  Set KNOWLEDGE_SCORE_FLOOR between the control ceiling and the LOWEST TP dense_top1.")


if __name__ == "__main__":
    main()
