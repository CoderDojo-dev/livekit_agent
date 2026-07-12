"""Offline RRF and metadata-filter tests."""
from knowledge_service.hybrid import reciprocal_rank_fusion
from knowledge_service.retriever import Passage, SearchFilters, build_qdrant_filter


def _passage(chunk_id: str, score: float, source: str = "doc.md") -> Passage:
    return Passage(
        text=f"passage {chunk_id}",
        source=source,
        score=score,
        language="fr",
        document_type="product",
        metadata={"chunk_id": chunk_id, "title": "Doc", "version": 1},
    )


def test_rrf_rewards_results_present_in_both_channels() -> None:
    dense = [_passage("a", 0.9), _passage("b", 0.8)]
    sparse = [_passage("b", 0.7), _passage("c", 0.6)]
    fused = reciprocal_rank_fusion(dense, sparse, top_k=3)
    assert fused[0].metadata["chunk_id"] == "b"
    assert fused[0].metadata["retrieval_channels"] == ["dense", "sparse"]
    assert fused[0].metadata["rrf_score"] > fused[1].metadata["rrf_score"]


def test_qdrant_filter_contains_active_and_metadata_conditions() -> None:
    query_filter = build_qdrant_filter(
        SearchFilters(
            language="fr",
            document_type="product",
            applicable_plans=("flexi", "postpaid"),
        )
    )
    assert len(query_filter.must) == 4
    keys = {condition.key for condition in query_filter.must}
    assert keys == {"active", "language", "document_type", "applicable_plans"}
