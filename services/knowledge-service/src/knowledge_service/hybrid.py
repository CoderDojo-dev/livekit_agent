"""Postgres sparse retrieval and reciprocal-rank fusion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from knowledge_service.retriever import Passage, SearchFilters


@dataclass(frozen=True, slots=True)
class RankedPassage:
    passage: Passage
    rank: int


class PostgresSparseRetriever:
    """Indexed PostgreSQL FTS over active knowledge chunks."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters,
    ) -> list[Passage]:
        where = [
            "c.active IS TRUE",
            "d.status = 'ready'",
            "c.search_vector @@ websearch_to_tsquery('simple', :query)",
        ]
        params: dict[str, Any] = {"query": query, "limit": top_k}
        if filters.language:
            where.append("d.language = :language")
            params["language"] = filters.language
        if filters.document_type:
            where.append("d.document_type = :document_type")
            params["document_type"] = filters.document_type
        if filters.applicable_plans:
            where.append(
                """(
                    (
                        jsonb_typeof(d.metadata -> 'applicable_plans') = 'array'
                        AND EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements_text(
                                d.metadata -> 'applicable_plans'
                            ) AS plan(value)
                            WHERE plan.value = ANY(CAST(:applicable_plans AS text[]))
                        )
                    )
                    OR d.metadata ->> 'applicable_plans'
                        = ANY(CAST(:applicable_plans AS text[]))
                )"""
            )
            params["applicable_plans"] = list(filters.applicable_plans)

        statement = text(
            f"""
            SELECT
                c.id AS chunk_id,
                c.text AS passage_text,
                c.checksum AS chunk_checksum,
                d.source,
                d.title,
                d.version,
                d.language,
                d.document_type,
                d.metadata,
                ts_rank_cd(
                    c.search_vector,
                    websearch_to_tsquery('simple', :query)
                ) AS sparse_score
            FROM knowledge.chunks AS c
            JOIN knowledge.documents AS d ON d.id = c.document_id
            WHERE {' AND '.join(where)}
            ORDER BY sparse_score DESC, c.ordinal ASC
            LIMIT :limit
            """
        )
        with self._session_factory() as session:
            rows = session.execute(statement, params).mappings().all()
        return [
            Passage(
                text=row["passage_text"],
                source=row["source"],
                score=float(row["sparse_score"]),
                language=row["language"],
                document_type=row["document_type"],
                metadata={
                    **dict(row["metadata"] or {}),
                    "chunk_id": str(row["chunk_id"]),
                    "checksum": row["chunk_checksum"],
                    "title": row["title"],
                    "version": row["version"],
                    "retrieval_channel": "sparse",
                },
            )
            for row in rows
        ]


def reciprocal_rank_fusion(
    dense: list[Passage],
    sparse: list[Passage],
    *,
    top_k: int,
    rank_constant: int = 60,
) -> list[Passage]:
    """Fuse ranked lists by stable chunk identity using standard RRF."""
    if rank_constant < 1:
        raise ValueError("rank_constant must be positive")
    scores: dict[str, float] = {}
    passages: dict[str, Passage] = {}
    channels: dict[str, set[str]] = {}

    for channel, ranked in (("dense", dense), ("sparse", sparse)):
        for rank, passage in enumerate(ranked, start=1):
            key = str(
                passage.metadata.get("chunk_id")
                or passage.metadata.get("checksum")
                or f"{passage.source}:{passage.text}"
            )
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank_constant + rank)
            channels.setdefault(key, set()).add(channel)
            passages.setdefault(key, passage)

    ordered = sorted(scores, key=lambda key: (-scores[key], key))[:top_k]
    return [
        Passage(
            text=passages[key].text,
            source=passages[key].source,
            score=scores[key],
            language=passages[key].language,
            document_type=passages[key].document_type,
            metadata={
                **passages[key].metadata,
                "retrieval_channels": sorted(channels[key]),
                "rrf_score": scores[key],
            },
        )
        for key in ordered
    ]
