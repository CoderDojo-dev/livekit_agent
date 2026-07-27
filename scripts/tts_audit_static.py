"""Compte les chaines TTS SANS passer un seul appel et SANS synthetiser.

Emplacement cible : scripts/tts_audit_static.py

A lancer dans le conteneur agent-worker. Ne synthetise AUCUN caractere, donc ne
consomme AUCUN credit Cartesia : il ne fait que construire les objets et compter.
Seules des connexions peuvent etre prechauffees (gratuit, mais c'est justement ce
que l'on veut mesurer).

Usage
  TTS_AUDIT=1 TTS_AUDIT_LOG=/tmp/tts_static.jsonl python3 scripts/tts_audit_static.py
"""

from __future__ import annotations

import os
import sys

os.environ["TTS_AUDIT"] = "1"
os.environ["TTS_AUDIT_LOG"] = "/tmp/tts_static.jsonl"

for candidate in ("/app/apps/agent-worker/src", "apps/agent-worker/src"):
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

BAR = "-" * 74


def main():
    from providers.tts_audit import install_tts_audit

    if not install_tts_audit():
        print("TTS_AUDIT n'est pas a 1 : audit inactif.")
        return 2

    from config.settings import get_settings

    settings = get_settings()

    print(BAR)
    print("A. CE QUI SERA REELLEMENT FACTURE")
    print(BAR)
    env_model = os.getenv("CARTESIA_TTS_MODEL", "")
    effective = env_model or "sonic-3 (defaut code dans providers/tts.py)"
    print("settings.cartesia_tts_model      : " + str(settings.cartesia_tts_model)
          + "   <- JAMAIS LU par providers/tts.py")
    print("CARTESIA_TTS_MODEL (env)         : " + (env_model or "(absent)"))
    print("modele effectivement facture     : " + effective)
    print("TTS_PRIMARY                      : " + os.getenv("TTS_PRIMARY", "(absent -> cartesia)"))
    print("preemptive_generation            : " + str(settings.preemptive_generation)
          + "   <- si True, l'audio jete est FACTURE")
    print("use_tts_aligned_transcript       : True (code en dur, session_factory.py)")

    keys = {
        "CARTESIA_API_KEY": "cartesia",
        "ELEVEN_API_KEY": "elevenlabs",
        "INWORLD_API_KEY": "inworld",
        "SMALLEST_API_KEY": "smallestai",
    }
    present = [name for name, _ in keys.items() if os.getenv(name, "")]
    print("cles TTS presentes               : " + str([keys[k] for k in present]))
    if len(present) < 2:
        print("  ATTENTION : un seul provider -> le FallbackAdapter n'a AUCUN")
        print("  recours, et chaque incident resynthetise la phrase entiere.")

    print("")
    print(BAR)
    print("B. COMBIEN DE CHAINES TTS POUR UN SEUL APPEL")
    print(BAR)

    built = []

    try:
        from providers.session_factory import build_agent_session

        build_agent_session(settings, "fr")
        built.append("session (session_factory.build_agent_session)")
        print("  + 1 chaine : la session")
    except Exception as exc:
        print("  session non construite (" + type(exc).__name__ + ") : " + str(exc)[:120])

    personas = (
        ("agents.triage_agent", "TriageAgent"),
        ("agents.billing_agent", "BillingAgent"),
        ("agents.account_services_agent", "AccountServicesAgent"),
        ("agents.technical_agent", "TechnicalAgent"),
        ("agents.manager_agent", "ManagerAgent"),
    )
    for module_name, class_name in personas:
        try:
            module = __import__(module_name, fromlist=[class_name])
            klass = getattr(module, class_name)
            klass(language="fr")
            built.append(class_name)
            print("  + 1 chaine : " + class_name + " (build_persona_tts dans __init__)")
        except Exception as exc:
            print("  " + class_name + " non construit (" + type(exc).__name__ + ") : "
                  + str(exc)[:100])

    print("")
    print("TOTAL de chaines TTS Cartesia vivantes : " + str(len(built)))
    print("Attendu pour un appel mono-client      : 1")
    if len(built) > 1:
        print("=> Chaque transfert en ajoute une, et AUCUNE n'est fermee (pas d'aclose).")
    print("")
    print("Detail evenement par evenement : " + os.environ["TTS_AUDIT_LOG"])
    print("Rapport : python3 scripts/tts_audit_report.py " + os.environ["TTS_AUDIT_LOG"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
