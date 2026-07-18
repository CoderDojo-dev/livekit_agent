"""Corpus de connaissances en français (section 1.3 du cookbook : un corpus français natif).

La couche conversationnelle est multilingue ; ce corpus système est désormais en français.
Le LLM recherche en français et répond dans la langue de l'appelant, en citant la source
retournée. Le contenu reflète les offres/procédures/FAQ de Tunisie Telecom avec les codes USSD
réels et les montants en TND.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """Un passage de connaissances récupérable avec une référence de source citable."""

    doc_id: str
    title: str
    text: str
    source: str


CORPUS: tuple[Document, ...] = (
    Document(
        doc_id="offer-flexi",
        title="Forfait Flexi postpaid",
        text=(
            "Le Forfait Flexi est un forfait mobile postpayé. Le palier à 25 TND inclut 20 Go de "
            "données nationales, des appels illimités vers les numéros Tunisie Telecom, et 120 "
            "minutes vers les autres réseaux nationaux. La facturation est mensuelle. Vous pouvez "
            "consulter votre données restantes en composant le *111#."
        ),
        source="offers/forfait-flexi",
    ),
    Document(
        doc_id="proc-roaming",
        title="Activer l'itinérance internationale",
        text=(
            "Pour activer l'itinérance internationale sur une ligne postpayée, composez le *140# "
            "et suivez le menu, ou activez l'itinérance dans l'application My Tunisie Telecom. "
            "L'activation de l'itinérance peut prendre jusqu'à 30 minutes. Les pass "
            "d'itinérance journaliers sont facturés en TND selon la zone de destination."
        ),
        source="procedures/roaming-activation",
    ),
    Document(
        doc_id="faq-data",
        title="Les données mobiles ne fonctionnent pas",
        text=(
            "Si les données mobiles ne fonctionnent pas, activez puis désactivez le mode "
            "avion, puis vérifiez que l'APN est réglé sur « internet ». Confirmez qu'il reste des "
            "données en composant le *111#. Si le problème persiste dans votre zone, il peut "
            "s'agir d'un incident réseau connu."
        ),
        source="faq/data-troubleshooting",
    ),
    Document(
        doc_id="faq-billing",
        title="Facture et cycle de facturation",
        text=(
            "Les factures postpayées sont émises mensuellement et sont dues 15 jours après "
            "émission. Vous pouvez consulter le montant et la date d'échéance de votre dernière "
            "facture en demandant à l'assistant, dans l'application My Tunisie Telecom, ou en "
            "composant le *888#. Un report de paiement peut être demandé pour les comptes "
            "éligibles."
        ),
        source="faq/billing-cycle",
    ),
    Document(
        doc_id="proc-plan-change",
        title="Changer de forfait mobile",
        text=(
            "Pour changer de forfait mobile, le changement prend effet au début du prochain "
            "cycle de facturation. Les rétrogradations conservent votre numéro et votre solde "
            "restant. Certains forfaits promotionnels exigent une période d'engagement minimale "
            "avant qu'un changement soit autorisé."
        ),
        source="procedures/plan-change",
    ),
)
