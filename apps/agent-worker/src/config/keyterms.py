"""Anglicismes techniques que le modèle STT francais ne connait pas.

Deepgram nova-3 amplifie un terme fourni en keyterm; l'effet est utile UNIQUEMENT pour
les mots absents du lexique de la langue de reconnaissance. Un mot francais courant
(facture, solde, recharge) est deja connu: le booster n'apporte rien et deplace la
frontiere de decision au detriment de ses voisins phonetiques.

Regle d'entree dans cette liste, verifiable en revue:
  1. le mot est anglais ou un sigle technique, ET
  2. il a ete observe mal transcrit sur un appel reel, OU il est phonetiquement proche
     d'un mot francais frequent (roaming/literances, data/data-t, hotspot/haute-spote).
Tout le reste reste dehors. La liste doit rester courte: chaque terme superflu coute
de la precision sur les autres.
"""
from __future__ import annotations

from collections.abc import Iterable

# Cap dur. Au-dela, la requete devient bruyante et Deepgram degrade la reconnaissance.
MAX_KEYTERMS = 30

# Anglicismes du support telecom, en anglais uniquement. Aucun nom de marque,
# aucun mot francais, aucun mot arabe.
TELECOM_KEYTERMS: tuple[str, ...] = (
    "roaming",
    "data",
    "wifi",
    "hotspot",
    "tethering",
    "modem",
    "router",
    "bandwidth",
    "upload",
    "download",
    "prepaid",
    "postpaid",
    "top-up",
    "ADSL",
    "VDSL",
    "LTE",
    "4G",
    "5G",
    "APN",
    "SIM",
    "eSIM",
    "PUK",
    "IMEI",
    "MSISDN",
)


def keyterms_for(extra: Iterable[str] = ()) -> list[str]:
    """Liste finale envoyee au STT: base + termes ponctuels, dedupliquee et plafonnee.

    L'ordre est stable (base d'abord) pour que deux appels identiques produisent la meme
    requete: une difference de liste change les resultats de reconnaissance et rendrait
    tout diagnostic non reproductible.
    """
    seen: set[str] = set()
    result: list[str] = []
    for term in (*TELECOM_KEYTERMS, *extra):
        cleaned = (term or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= MAX_KEYTERMS:
            break
    return result
