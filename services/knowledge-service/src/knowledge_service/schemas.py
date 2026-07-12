"""Validated wire DTOs for dense knowledge retrieval."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """A multilingual knowledge-base search query."""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)


class PassageModel(BaseModel):
    """A grounded passage with citation and classification metadata."""

    text: str
    source: str
    score: float
    language: str
    document_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Ranked dense passages; every result carries its source."""

    passages: list[PassageModel]
