"""Wire DTOs for the knowledge-service."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """A knowledge-base search query (English, per cookbook section 1).

    The optional filters narrow the candidate set BEFORE vector scoring, using the Qdrant payload
    indexes. Leave them unset to search the whole corpus - filtering by `language` in particular
    is usually wrong here, because the corpus is English while callers speak fr/ar/en and E5's
    aligned space is what lets a French question find an English procedure.
    """

    query: str
    top_k: int = 4
    language: str | None = None
    document_type: str | None = None
    region: str | None = None
    applicable_plans: list[str] | None = None
    product_codes: list[str] | None = None
    # E5 cosine scores cluster ~0.7-1.0 (low-temperature InfoNCE); a threshold copied from
    # another model will either filter nothing or everything. Unset = no cutoff.
    min_score: float | None = None

    def filters(self) -> dict:
        """Only the set filters, as the retriever expects them."""
        raw = {
            "language": self.language,
            "document_type": self.document_type,
            "region": self.region,
            "applicable_plans": self.applicable_plans,
            "product_codes": self.product_codes,
        }
        return {key: value for key, value in raw.items() if value}


class PassageModel(BaseModel):
    """A single grounded passage with everything needed to cite it to the caller.

    `source`/`title`/`version` let the agent say *where* an answer came from; `language` and
    `document_type` let the caller-facing layer (and phase 5's filters) reason about fit.
    """

    text: str
    source: str
    score: float
    title: str = ""
    language: str = ""
    document_type: str = ""
    version: int = 0
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Ranked passages for a query; every passage carries a source (Blueprint section 7.6)."""

    passages: list[PassageModel]


class UploadResponse(BaseModel):
    """Result of a document upload (and its ingestion, when requested)."""

    source: str
    status: str  # ingested | unchanged | stored | failed
    document_id: str | None = None
    version: int = 0
    chunks: int = 0
    indexed: int = 0
    message: str = ""


class DocumentSummary(BaseModel):
    """One document in the corpus, as the operator sees it."""

    document_id: str
    source: str
    title: str = ""
    language: str = ""
    document_type: str = ""
    version: int = 1
    status: str = ""
    chunks: int = 0
    checksum: str = ""


class DocumentListResponse(BaseModel):
    """The corpus inventory: what is actually searchable right now."""

    documents: list[DocumentSummary]
    total_documents: int = 0
    total_chunks: int = 0


class PurgeResponse(BaseModel):
    """Result of removing a document from index, records, and bucket."""

    source: str
    documents_archived: int = 0
    chunks_deactivated: int = 0
    points_removed: int = 0
    object_removed: bool = False
