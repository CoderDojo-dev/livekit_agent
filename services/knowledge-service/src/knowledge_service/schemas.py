"""Validated wire DTOs for filtered hybrid retrieval."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)
    language: Literal["fr", "ar", "en", "multilingual", "und"] | None = None
    document_type: str | None = Field(default=None, min_length=1, max_length=80)
    applicable_plans: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("applicable_plans")
    @classmethod
    def normalize_plans(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values if value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("applicable_plans must not contain duplicates")
        return normalized


class PassageModel(BaseModel):
    text: str
    source: str
    score: float
    language: str
    document_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    passages: list[PassageModel]
