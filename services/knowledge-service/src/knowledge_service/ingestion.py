"""Knowledge ingestion: MinIO -> parse -> chunk -> embed -> Postgres + Qdrant (RAG phase 3).

Postgres is the system of record. Qdrant is a derived, rebuildable index whose point id IS
`knowledge.chunks.qdrant_point_id`, so the two can always be reconciled. Every chunk write also
enqueues a `knowledge.sync_outbox` row, so a Qdrant outage degrades to "the index is stale"
(replayable by the phase 6 outbox worker) rather than "Postgres and Qdrant silently disagree".

Idempotency is checksum-based at two levels:
  * document - re-ingesting unchanged bytes is a no-op, so a nightly sweep costs nothing and
    never re-embeds a corpus.
  * version  - changed bytes create version N+1 and deactivate the previous version's chunks,
    so retrieval never mixes two revisions of the same procedure.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from knowledge_service.embeddings import LocalEmbedder, get_embedder
from knowledge_service.minio_store import KnowledgeStore, get_knowledge_store
from knowledge_service.parsers import (
    SUPPORTED_SUFFIXES,
    ParseError,
    extract_text,
    is_supported,
)
from knowledge_service.qdrant_store import get_client, qdrant_collection
from persistence.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
    KnowledgeSyncOutbox,
)

logger = logging.getLogger(__name__)

# knowledge.documents.language CHECK constraint vocabulary.
_LANGUAGES = ("fr", "ar", "en", "multilingual", "und")

# E5 truncates at 512 tokens. Budget in CHARACTERS because token density differs sharply by
# script (Arabic packs far fewer characters per token than French), and silently truncating a
# chunk would drop the end of a procedure from the index.
CHUNK_MAX_CHARS = int(os.getenv("KNOWLEDGE_CHUNK_MAX_CHARS", "1200"))
CHUNK_OVERLAP_CHARS = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP_CHARS", "150"))
EMBED_BATCH = int(os.getenv("KNOWLEDGE_EMBED_BATCH", "32"))

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_H1 = re.compile(r"^#\s+(.+)$", re.M)
_ARABIC = re.compile(r"[\u0600-\u06FF]")


@dataclass
class DocumentMeta:
    """What the parser recovered about a source object."""

    title: str
    language: str
    document_type: str
    extra: dict = field(default_factory=dict)


@dataclass
class IngestResult:
    """Outcome for one object key."""

    key: str
    status: str  # ingested | unchanged | failed
    document_id: uuid.UUID | None = None
    version: int = 0
    chunks: int = 0
    error: str | None = None


# ---- pure helpers (offline-testable) ----
def checksum(data: bytes | str) -> str:
    """SHA-256 of the exact bytes we ingested (the idempotency key for a revision)."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a simple `key: value` front-matter block from the body (no YAML dependency)."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            continue
        if "," in value:
            meta[key] = [item.strip() for item in value.split(",") if item.strip()]
        else:
            meta[key] = value
    return meta, text[match.end():].strip()


def detect_language(text: str, declared: str | None = None) -> str:
    """Trust the declared language; otherwise infer script. Never invent an unsupported code."""
    if declared:
        candidate = str(declared).strip().lower()[:12]
        if candidate in _LANGUAGES:
            return candidate
    if not text:
        return "und"
    arabic = len(_ARABIC.findall(text))
    if arabic and arabic / max(len(text), 1) > 0.05:
        return "ar"
    if re.search(r"[àâçéèêëîïôûùüÿœ]", text, re.I):
        return "fr"
    if re.search(r"[a-z]", text, re.I):
        return "en"
    return "und"


def infer_document_type(key: str, declared: str | None = None) -> str:
    """Declared type wins; else the bucket's top-level folder is the taxonomy (offers/, faq/...)."""
    if declared:
        return str(declared).strip().lower()[:80]
    parts = [part for part in key.split("/") if part]
    if len(parts) > 1:
        return parts[0].lower()[:80]
    return "general"


def infer_title(body: str, key: str, declared: str | None = None) -> str:
    """Declared title wins; else the first markdown H1; else a readable form of the filename."""
    if declared:
        return str(declared).strip()[:300]
    heading = _H1.search(body)
    if heading:
        return heading.group(1).strip()[:300]
    stem = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return stem.replace("-", " ").replace("_", " ").strip()[:300] or key[:300]


def parse_document(key: str, raw: bytes) -> tuple[DocumentMeta, str]:
    """Turn stored bytes into (metadata, body), whatever the source format.

    Text extraction is format-aware (PDF/DOCX/CSV/JSON/Markdown) and raises ParseError rather
    than yielding an empty body, so an unreadable file becomes a recorded failure instead of a
    document that silently matches nothing.
    """
    text = extract_text(key, raw)
    front, body = parse_front_matter(text)
    language = detect_language(body, front.get("language"))
    meta = DocumentMeta(
        title=infer_title(body, key, front.get("title")),
        language=language,
        document_type=infer_document_type(key, front.get("document_type") or front.get("type")),
        extra={
            key_: value
            for key_, value in front.items()
            if key_ not in {"title", "language", "document_type", "type"}
        },
    )
    return meta, body


def estimate_tokens(text: str) -> int:
    """Conservative token estimate (>=1, satisfying the chunks.token_count > 0 CHECK).

    A whitespace count under-reads Arabic and over-reads code-like text, so take the larger of
    word-count and a chars/4 heuristic. It is an estimate, used for observability - the real
    truncation guard is the character budget applied while chunking.
    """
    words = len(text.split())
    return max(1, words, len(text) // 4)


def chunk_text(body: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split a body into overlapping passages that respect paragraph boundaries.

    Paragraph-first keeps a procedure's steps together; the overlap carries context across a cut
    so a passage that begins mid-procedure still retrieves. A single oversized paragraph is hard
    split rather than dropped.
    """
    if not body.strip():
        return []
    paragraphs = [para.strip() for para in re.split(r"\n\s*\n", body) if para.strip()]
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        while len(para) > max_chars:  # oversized paragraph: hard split, never drop
            flush()
            chunks.append(para[:max_chars].strip())
            para = para[max(0, max_chars - overlap):]
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            flush()
            tail = chunks[-1][-overlap:] if chunks and overlap > 0 else ""
            current = f"{tail}\n\n{para}".strip() if tail else para
    flush()
    return chunks


def qdrant_payload(document: KnowledgeDocument, chunk_text_value: str, ordinal: int) -> dict:
    """The filterable payload stored beside a vector (phase 5 pre-filters on these keys)."""
    extra = document.metadata_json or {}
    return {
        "document_id": str(document.id),
        "source": document.source,
        "title": document.title,
        "version": document.version,
        "language": document.language,
        "document_type": document.document_type,
        "checksum": document.checksum,
        "ordinal": ordinal,
        "active": True,
        "text": chunk_text_value,
        "applicable_plans": extra.get("applicable_plans", []),
        "product_codes": extra.get("product_codes", []),
        "region": extra.get("region", ""),
        "valid_from": extra.get("valid_from", ""),
        "valid_until": extra.get("valid_until", ""),
    }


# ---- ingestion ----
def _latest_version(session: Session, source: str) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.max(KnowledgeDocument.version), 0)).where(
                KnowledgeDocument.source == source
            )
        )
        or 0
    )


def _unchanged(session: Session, source: str, digest: str) -> KnowledgeDocument | None:
    """A ready document with identical bytes: re-ingesting it would be wasted embedding."""
    return session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.source == source,
            KnowledgeDocument.checksum == digest,
            KnowledgeDocument.status == "ready",
        )
    )


def _deactivate_previous(session: Session, source: str, keep_document_id: uuid.UUID) -> list[uuid.UUID]:
    """Retire earlier revisions' chunks so retrieval never mixes two versions of a procedure."""
    stale = list(
        session.scalars(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeDocument.source == source,
                KnowledgeDocument.id != keep_document_id,
                KnowledgeChunk.active.is_(True),
            )
        )
    )
    point_ids: list[uuid.UUID] = []
    for chunk in stale:
        chunk.active = False
        point_ids.append(chunk.qdrant_point_id)
        session.add(
            KnowledgeSyncOutbox(
                aggregate_type="chunk",
                aggregate_id=chunk.id,
                operation="delete",
                payload={"qdrant_point_id": str(chunk.qdrant_point_id)},
            )
        )
    for document in session.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.source == source,
            KnowledgeDocument.id != keep_document_id,
            KnowledgeDocument.status == "ready",
        )
    ):
        document.status = "archived"
    return point_ids


def ingest_object(
    session: Session,
    store: KnowledgeStore,
    key: str,
    embedder: LocalEmbedder,
    qdrant_client=None,
) -> IngestResult:
    """Ingest one object key. Returns a result rather than raising, so one bad file cannot
    abort a whole corpus run; the failure is recorded on the ingestion job."""
    raw = store.get(key)
    digest = checksum(raw)

    existing = _unchanged(session, key, digest)
    if existing is not None:
        return IngestResult(key=key, status="unchanged", document_id=existing.id, version=existing.version)

    meta, body = parse_document(key, raw)
    passages = chunk_text(body)
    if not passages:
        return IngestResult(key=key, status="failed", error="document produced no chunks")

    document = KnowledgeDocument(
        source=key,
        title=meta.title,
        language=meta.language,
        document_type=meta.document_type,
        checksum=digest,
        version=_latest_version(session, key) + 1,
        status="processing",
        minio_uri=store.uri(key),
        metadata_json=meta.extra,
    )
    session.add(document)
    session.flush()  # assign document.id before chunks reference it

    vectors: list[list[float]] = []
    for start in range(0, len(passages), EMBED_BATCH):
        vectors.extend(embedder.embed_passages(passages[start : start + EMBED_BATCH]))

    points: list[tuple[uuid.UUID, list[float], dict]] = []
    for ordinal, (passage, vector) in enumerate(zip(passages, vectors)):
        point_id = uuid.uuid4()
        chunk = KnowledgeChunk(
            document_id=document.id,
            ordinal=ordinal,
            text_content=passage,
            token_count=estimate_tokens(passage),
            checksum=checksum(passage),
            qdrant_point_id=point_id,
            embedding_model=embedder.model_name,
            embedding_dimensions=embedder.dimensions,
            metadata_json={"language": meta.language, "document_type": meta.document_type},
            active=True,
        )
        session.add(chunk)
        session.flush()
        payload = qdrant_payload(document, passage, ordinal)
        points.append((point_id, vector, payload))
        session.add(
            KnowledgeSyncOutbox(
                aggregate_type="chunk",
                aggregate_id=chunk.id,
                operation="upsert",
                payload={"qdrant_point_id": str(point_id)},
            )
        )

    retired = _deactivate_previous(session, key, document.id)
    document.status = "ready"

    if qdrant_client is not None:
        _upsert_points(qdrant_client, points, retired)

    return IngestResult(
        key=key, status="ingested", document_id=document.id, version=document.version, chunks=len(points)
    )


def _upsert_points(client, points, retired_point_ids) -> None:
    """Push vectors to Qdrant. The outbox already holds the intent, so a failure here is
    recoverable: it is logged and replayed, never silently lost."""
    from qdrant_client.models import PointStruct

    collection = qdrant_collection()
    try:
        if points:
            client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(id=str(pid), vector=vector, payload=payload)
                    for pid, vector, payload in points
                ],
            )
        if retired_point_ids:
            client.delete(
                collection_name=collection,
                points_selector=[str(pid) for pid in retired_point_ids],
            )
    except Exception as exc:
        logger.error("qdrant sync failed (outbox will replay): %s", exc)


def ingest_bucket(session: Session, keys: list[str] | None = None) -> list[IngestResult]:
    """Ingest every supported object in the knowledge bucket (or just ``keys``)."""
    store = get_knowledge_store()
    embedder = get_embedder()
    try:
        client = get_client()
    except Exception as exc:
        logger.warning("qdrant unavailable at ingestion time (%s); outbox will carry the sync", exc)
        client = None

    targets = keys if keys is not None else store.list_keys()
    results: list[IngestResult] = []

    for key in targets:
        job = KnowledgeIngestionJob(
            status="running",
            source_object_key=key,
            embedding_model=embedder.model_name,
            embedding_dimensions=embedder.dimensions,
            started_at=datetime.now(UTC),
        )
        session.add(job)
        session.flush()
        try:
            result = ingest_object(session, store, key, embedder, client)
            job.document_id = result.document_id
            job.document_count = 1 if result.status == "ingested" else 0
            job.chunk_count = result.chunks
            job.embedded_count = result.chunks
            job.status = "succeeded" if result.status != "failed" else "failed"
            job.error_details = result.error
            job.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:  # one bad object must not abort the corpus
            session.rollback()
            logger.exception("ingestion failed for %s", key)
            result = IngestResult(key=key, status="failed", error=str(exc))
            failed = KnowledgeIngestionJob(
                status="failed",
                source_object_key=key,
                embedding_model=embedder.model_name,
                embedding_dimensions=embedder.dimensions,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error_details=str(exc)[:4000],
            )
            session.add(failed)
            session.commit()
        results.append(result)
        logger.info("%s -> %s (%d chunks)", key, result.status, result.chunks)

    return results


def run() -> None:
    """Console-script entrypoint: `knowledge-ingest`."""
    logging.basicConfig(level=logging.INFO)
    from persistence.engine import session_scope

    with session_scope() as session:
        results = ingest_bucket(session)

    ingested = sum(1 for r in results if r.status == "ingested")
    unchanged = sum(1 for r in results if r.status == "unchanged")
    failed = [r for r in results if r.status == "failed"]
    chunks = sum(r.chunks for r in results)
    print(f"INGESTED={ingested} UNCHANGED={unchanged} FAILED={len(failed)} CHUNKS={chunks}")
    for result in failed:
        print(f"  FAILED {result.key}: {result.error}")
    print("KNOWLEDGE_INGEST_OK" if not failed else "KNOWLEDGE_INGEST_PARTIAL")


# ---- upload pipeline (RAG phase 5a) ----
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

MAX_UPLOAD_BYTES = int(os.getenv("KNOWLEDGE_MAX_UPLOAD_MB", "25")) * 1024 * 1024


def safe_key(filename: str, document_type: str = "general") -> str:
    """Build a bucket key from an untrusted filename.

    Path separators and traversal are stripped rather than escaped: an uploaded name must never
    be able to address a key outside its folder. The folder doubles as the document_type
    taxonomy that `infer_document_type` reads back.
    """
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = _SAFE_NAME.sub("-", name).strip("-.") or "document"
    folder = _SAFE_NAME.sub("-", (document_type or "general").strip().lower()).strip("-.") or "general"
    return f"{folder}/{name}"


def store_and_ingest(
    raw: bytes,
    filename: str,
    document_type: str = "general",
    auto_ingest: bool = True,
) -> dict:
    """Write an uploaded file to the knowledge bucket and run the pipeline for that key alone.

    Single-key ingestion (never a full bucket rescan) keeps an upload O(1) instead of O(corpus),
    and the outbox is drained immediately afterwards so the document is searchable when this
    returns - no manual CLI step, which is what blocked iterative testing.
    """
    if not raw:
        raise ValueError("uploaded file is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"file is {len(raw) / 1_048_576:.1f} MB; the limit is {MAX_UPLOAD_BYTES // 1_048_576} MB"
        )

    key = safe_key(filename, document_type)
    if not is_supported(key):
        raise ValueError(
            f"unsupported format for {key!r}; supported: {', '.join(SUPPORTED_SUFFIXES)}"
        )

    store = get_knowledge_store()
    store.put(key, raw, content_type="application/octet-stream")

    if not auto_ingest:
        return {"source": key, "status": "stored", "chunks": 0, "indexed": 0,
                "message": "stored; ingestion not requested"}

    from knowledge_service.retriever import reset_retriever  # local: avoids an import cycle
    from knowledge_service.sync_worker import drain
    from persistence.engine import session_scope

    with session_scope() as session:
        results = ingest_bucket(session, keys=[key])
    result = results[0] if results else IngestResult(key=key, status="failed", error="no result")

    indexed = 0
    if result.status != "failed":
        with session_scope() as session:
            counts = drain(session)
        indexed = counts.get("upserted", 0)
        reset_retriever()  # the index just changed; drop any 'collection is empty' memo

    return {
        "source": key,
        "status": result.status,
        "document_id": str(result.document_id) if result.document_id else None,
        "version": result.version,
        "chunks": result.chunks,
        "indexed": indexed,
        "message": result.error or f"{result.status}: {result.chunks} chunk(s), {indexed} indexed",
    }
