"""Wire DTOs for the knowledge-service."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """A knowledge-base search query (English, per cookbook section 1)."""

    query: str
    top_k: int = 4


class PassageModel(BaseModel):
    """A single grounded passage with its source reference."""

    text: str
    source: str
    score: float


class SearchResponse(BaseModel):
    """Ranked passages for a query; every passage carries a source (Blueprint section 7.6)."""

    passages: list[PassageModel]