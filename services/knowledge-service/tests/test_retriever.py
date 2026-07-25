"""Offline retrieval tests (no network/SDK)."""
from __future__ import annotations

from knowledge_service.retriever import LexicalRetriever

retriever = LexicalRetriever()


def test_roaming_query_returns_roaming_doc_with_source() -> None:
    # The system corpus is French-native (corpus.py: "un corpus français natif"), and the
    # LexicalRetriever is a term-overlap stub for offline tests only. Queries are therefore French to
    # overlap the corpus - production cross-lingual retrieval is the dense E5 path, not this stub.
    passages = retriever.search("comment activer l'itinérance internationale à l'étranger", top_k=3)
    assert passages
    assert passages[0].source == "procedures/roaming-activation"
    assert passages[0].score > 0


def test_billing_query_returns_billing_doc() -> None:
    passages = retriever.search("consulter le montant et la date d'échéance de ma facture", top_k=3)
    assert any(p.source == "faq/billing-cycle" for p in passages)


def test_unmatched_query_returns_empty() -> None:
    assert retriever.search("zxqw nonsense token", top_k=3) == []