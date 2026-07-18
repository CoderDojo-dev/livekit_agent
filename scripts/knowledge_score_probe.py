"""Calibrate the 3-layer gate against the REAL corpus (RAG phase 8.1).

Prints a markdown table, one row per query:
  | query | type | dense_top1 | max_bm25 | ce_top1 | gated_verdict | expected | PASS? |

After the table, prints two summary lines:
  lowest TP:  dense=.. bm25=.. ce=..
  highest noise: dense=.. bm25=.. ce=..

Usage (inside the knowledge-service container):
    python /app/scripts/knowledge_score_probe.py
"""
from __future__ import annotations

import sys

from knowledge_service.embeddings import get_embedder, get_sparse_embedder, hybrid_enabled
from knowledge_service.qdrant_store import get_client, qdrant_collection
from knowledge_service.retriever import SPARSE_MIN, QdrantE5Retriever
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
    try:
        from knowledge_service.ce_gate import ce_gate_enabled, get_ce_gate

        if ce_gate_enabled():
            ce_gate = get_ce_gate()
    except Exception:
        pass

    rows: list[dict] = []

    for query, qtype in queries:
        dense_top1 = 0.0
        max_bm25 = 0.0
        ce_top1 = 0.0

        # --- Ungated pass: read raw scores (E3) ---
        ungated = retriever.search(query, top_k=CANDIDATES, apply_gate=False)
        if ungated:
            dense_top1 = round(ungated[0].score, 4)

        if sparse is not None:
            try:
                sq = sparse.embed_query(query)
                resp = client.query_points(
                    collection_name=collection,
                    query=SparseVector(indices=list(sq.indices), values=list(sq.values)),
                    using="bm25",
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

        # --- Gated pass: production verdict (E3) ---
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
            "gated_verdict": gated_verdict,
            "expected": expected,
            "pass": pass_mark,
        })

    # --- Markdown table (E2) ---
    header = "| query | type | dense_top1 | max_bm25 | ce_top1 | gated_verdict | expected | PASS? |"
    sep = "|-------|------|-----------:|---------:|--------:|---------------|----------|-------|"
    print(f"FLOOR=0.82  SPARSE_MIN={SPARSE_MIN}  hybrid={'on' if sparse else 'OFF'}  CE={'on' if ce_gate else 'OFF'}")
    print()
    print(header)
    print(sep)
    for r in rows:
        print(
            f"| {r['query']} | {r['type']} | {r['dense_top1']:.4f} | {r['max_bm25']:.4f} "
            f"| {r['ce_top1']:.4f} | {r['gated_verdict']} | {r['expected']} | {r['pass']} |"
        )
    print()

    # --- Summary: calibration windows (E2) ---
    tp_rows = [r for r in rows if r["type"] == "tp"]
    noise_rows = [r for r in rows if r["type"] == "noise"]
    if tp_rows:
        lt = min(tp_rows, key=lambda r: r["dense_top1"])
        lb = min(tp_rows, key=lambda r: r["max_bm25"])
        lc = min(tp_rows, key=lambda r: r["ce_top1"])
        print(
            f"lowest TP:  dense={lt['dense_top1']:.4f} ({lt['query']})  "
            f"bm25={lb['max_bm25']:.4f} ({lb['query']})  "
            f"ce={lc['ce_top1']:.4f} ({lc['query']})"
        )
    if noise_rows:
        ht = max(noise_rows, key=lambda r: r["dense_top1"])
        hb = max(noise_rows, key=lambda r: r["max_bm25"])
        hc = max(noise_rows, key=lambda r: r["ce_top1"])
        print(
            f"highest noise: dense={ht['dense_top1']:.4f} ({ht['query']})  "
            f"bm25={hb['max_bm25']:.4f} ({hb['query']})  "
            f"ce={hc['ce_top1']:.4f} ({hc['query']})"
        )
    print()

    print("Calibration:")
    print("  Set KNOWLEDGE_SPARSE_MIN between the lowest TP max_bm25 and the highest noise max_bm25.")
    print("  Set KNOWLEDGE_CE_THRESHOLD between the lowest TP ce_top1 and the highest noise ce_top1.")
    print("  Set KNOWLEDGE_SCORE_FLOOR between the control ceiling and the LOWEST TP dense_top1.")


if __name__ == "__main__":
    main()
