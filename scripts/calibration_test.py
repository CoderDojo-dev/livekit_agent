"""Hardest French RAG calibration test — ungated dense scores only."""
from knowledge_service.embeddings import get_embedder
from knowledge_service.qdrant_store import get_client, qdrant_collection
from knowledge_service.retriever import QdrantE5Retriever

client = get_client()
retriever = QdrantE5Retriever(client, qdrant_collection(), get_embedder())

queries = [
    ("roaming exact",        "comment activer le roaming international", True),
    ("billing",              "ma facture est trop elevee ce mois-ci", True),
    ("pricing",              "combien coute le forfait Flexi a 25 TND", True),
    ("addons",               "c est quoi les options data boost nuit weekend", True),
    ("data issue",           "mon internet 4G ne marche plus", True),
    ("plan change",          "comment changer de forfait mobile", True),
    ("roaming signal",       "je n ai plus de signal depuis mon arrivee", True),
    ("fixed internet",       "quels sont les forfaits internet fixes", True),
    ("legal",                "delai de retractation droit de renoncer", False),
    ("portability",          "transferer mon numero vers Tunisie Telecom", True),
    ("USSD balance",         "code USSD pour consulter mon solde", True),
    ("eSIM",                 "est ce que lesim est disponible", False),
    ("SAV",                  "service apres vente telephone", False),
    ("appliance",            "reparation machine a laver", False),
    ("weather",              "meteo tunis aujourd hui", False),
    ("jobs",                 "recrutement Tunisie Telecom", False),
    ("hours",                "horaires ouverture agence", False),
    ("control EN",           "how do I fix my washing machine", False),
]

tpos, fpos, tneg, fneg = [], [], 0, 0

print(f"{'Query':<20} {'DenseTop':>10}  {'Gated':>6}  {'Expect':>6}  Status")
print("-" * 55)

for label, query, expect in queries:
    ungated = retriever.search(query, top_k=4, apply_gate=False)
    gated = retriever.search(query, top_k=4)
    g_count = len(gated)
    dense_top = round(ungated[0].score, 4) if ungated else 0.0
    has_result = g_count > 0

    if has_result and expect:
        tpos.append(dense_top)
        status = "OK"
    elif has_result and not expect:
        fpos.append(dense_top)
        status = "LEAK"
    elif not has_result and not expect:
        tneg += 1
        status = "GATED"
    else:
        fneg += 1
        status = "MISS"

    print(f"{label:<20} {dense_top:>10.4f}  {has_result!s:>6}  {expect!s:>6}  {status}")

print()
print("=" * 50)
print("  CALIBRATION")
print("=" * 50)
tpos.sort()
fpos.sort()
print(f"True positives (lowest): {tpos[0]:.4f}" if tpos else "No TPs")
print(f"Noise leaks (highest):   {fpos[-1]:.4f}" if fpos else "No leaks")
print(f"False negatives:         {fneg}")
print(f"True negatives (gated):  {tneg}")
print()
if tpos and fpos:
    window = fpos[-1] < tpos[0]
    print(f"Safe window exists:     {window}")
    if window:
        rec = round((fpos[-1] + tpos[0]) / 2, 4)
        print(f"Recommended FLOOR:      {rec}")
        print(f"Margin above noise:     {round(tpos[0] - fpos[-1], 4)}")
    else:
        print(f"INVERTED — lowest TP ({tpos[0]:.4f}) < highest FP ({fpos[-1]:.4f})")
        gap = round(tpos[0] - fpos[-1], 4)
        print(f"Gap: {gap}")
        if gap > -0.02:
            print("Tight but fixable: bump FLOOR slightly or accept narrow tradeoff")
        else:
            print("Structural overlap — need more content or a reranker")
