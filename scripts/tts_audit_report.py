"""Rapport de reconciliation de l'audit TTS.

Emplacement cible : scripts/tts_audit_report.py

Lit le JSONL produit par providers/tts_audit.py et repond a une seule question :
combien de caracteres ont ete ENVOYES a Cartesia, contre combien ont ete
reellement JOUES au client ?

Usage
  python3 scripts/tts_audit_report.py /tmp/tts_audit.jsonl
  python3 scripts/tts_audit_report.py /tmp/tts_audit.jsonl --played 807

--played est la valeur tts_characters_count du usage_summary de votre log
worker. C'est la reference "audio reellement entendu".
"""

from __future__ import annotations

import collections
import json
import sys

BAR = "-" * 74


def load(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except Exception:
                continue
    return rows


def section(title):
    print("")
    print(BAR)
    print(title)
    print(BAR)


def main():
    if len(sys.argv) < 2:
        print("usage: tts_audit_report.py <fichier.jsonl> [--played N]")
        return 2
    path = sys.argv[1]
    played = None
    if "--played" in sys.argv:
        try:
            played = int(sys.argv[sys.argv.index("--played") + 1])
        except Exception:
            played = None

    rows = load(path)
    if not rows:
        print("Aucun evenement. TTS_AUDIT=1 est-il bien pose, et l'appel a-t-il eu lieu ?")
        return 1

    counts = collections.Counter(row.get("event", "?") for row in rows)

    created = [r for r in rows if r.get("event") == "adapter_created"]
    closed = counts.get("adapter_closed", 0)
    prewarm = counts.get("pool_prewarm_impl", 0)
    connect = counts.get("pool_connect", 0)
    opened = counts.get("stream_opened", 0)

    segments = [r for r in rows if r.get("event") in ("stream_segment", "chunked_synth")]
    total_chars = sum(int(r.get("chars", 0)) for r in segments)

    by_digest = collections.Counter()
    chars_by_digest = {}
    sample = {}
    for row in segments:
        digest = row.get("digest", "?")
        by_digest[digest] += 1
        chars_by_digest[digest] = int(row.get("chars", 0))
        sample.setdefault(digest, row.get("text", ""))
    unique_chars = sum(chars_by_digest.values())

    section("1. CHAINES TTS  (cause n2 : adaptateurs multiplies et jamais fermes)")
    print("chaines TTS construites          : " + str(len(created)))
    print("chaines TTS fermees              : " + str(closed))
    print("chaines FUITEES (jamais fermees) : " + str(max(0, len(created) - closed)))
    print("connexions PRECHAUFFEES          : " + str(prewarm))
    print("connexions ouvertes              : " + str(connect))
    print("")
    print("Attendu si tout va bien : 1 chaine par appel.")
    print("Qui a construit chaque chaine :")
    for row in created:
        who = row.get("built_by") or []
        origin = who[-3] if len(who) >= 3 else (who[0] if who else "?")
        print("  #" + str(row.get("adapter_id")) + "  providers="
              + str(row.get("providers")) + "  <- " + str(origin))

    section("2. SYNTHESES  (causes n1 et n3 : generation preemptive et reprises)")
    print("flux de synthese ouverts         : " + str(opened))
    print("syntheses envoyees au provider   : " + str(len(segments)))
    print("textes DISTINCTS synthetises     : " + str(len(by_digest)))
    if by_digest:
        ratio = len(segments) / float(len(by_digest))
        print("facteur de duplication           : x" + str(round(ratio, 2)))
    print("caracteres ENVOYES (factures)    : " + str(total_chars))
    print("caracteres si aucun doublon      : " + str(unique_chars))
    print("caracteres PAYES POUR RIEN       : " + str(total_chars - unique_chars))

    section("3. TEXTES RESYNTHETISES PLUSIEURS FOIS  (le gaspillage nomme)")
    repeated = [(d, n) for d, n in by_digest.most_common() if n > 1]
    if not repeated:
        print("Aucun texte synthetise deux fois. Causes n1 et n3 ECARTEES.")
    else:
        print(str(len(repeated)) + " textes ont ete synthetises plus d'une fois :")
        for digest, number in repeated[:12]:
            cost = number * chars_by_digest.get(digest, 0)
            print("  x" + str(number) + "  " + str(cost) + " car. factures  | "
                  + str(sample.get(digest, ""))[:70])

    section("4. VERDICT")
    if played:
        print("caracteres reellement JOUES      : " + str(played) + "  (usage_summary)")
        print("caracteres ENVOYES a Cartesia    : " + str(total_chars))
        if played > 0:
            print("SUR-SYNTHESE                     : x"
                  + str(round(total_chars / float(played), 2)))
        print("")
    leaked = max(0, len(created) - closed)
    verdicts = []
    if len(created) > 1:
        verdicts.append("CONFIRME cause n2 : " + str(len(created))
                        + " chaines TTS pour un appel au lieu d'une.")
    if leaked > 0:
        verdicts.append("CONFIRME fuite : " + str(leaked)
                        + " chaines jamais fermees (pools et sondes toujours vivants).")
    if repeated:
        verdicts.append("CONFIRME causes n1/n3 : " + str(total_chars - unique_chars)
                        + " caracteres factures pour de l'audio jamais joue.")
    if not verdicts:
        verdicts.append("Aucune anomalie detectee sur cet enregistrement.")
    for line in verdicts:
        print("  " + line)

    print("")
    print("Tous les evenements : " + str(dict(counts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
