"""Document parsing, metadata normalization, and deterministic chunking."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Mapping

from pypdf import PdfReader

_SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}
_TOKEN = re.compile(r"\S+")
_ARABIC = re.compile(r"[\u0600-\u06ff]")
_FRENCH_MARKERS = re.compile(
    r"\b(le|la|les|un|une|des|du|de|pour|avec|forfait|facture|mobile)\b",
    re.IGNORECASE,
)


class DocumentParseError(ValueError):
    """Raised when a knowledge object cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source: str
    title: str
    language: str
    document_type: str
    text: str
    checksum: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    ordinal: int
    text: str
    token_count: int
    checksum: str
    metadata: dict[str, object] = field(default_factory=dict)


def sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize line endings, invalid characters, and excessive whitespace."""
    normalized = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def detect_language(text: str) -> str:
    """Conservative language hint for FR/AR/EN; metadata can override it."""
    sample = text[:20_000]
    if not sample:
        return "und"
    arabic = len(_ARABIC.findall(sample))
    letters = sum(character.isalpha() for character in sample)
    if letters and arabic / letters >= 0.20:
        return "ar"
    if re.search(r"[àâçéèêëîïôûùüÿœ]", sample, re.IGNORECASE) or _FRENCH_MARKERS.search(sample):
        return "fr"
    if re.search(r"[A-Za-z]", sample):
        return "en"
    return "und"


def _metadata_value(metadata: Mapping[str, str], name: str) -> str | None:
    candidates = {
        name,
        name.replace("_", "-"),
        f"x-amz-meta-{name}",
        f"x-amz-meta-{name.replace('_', '-')}",
    }
    lowered = {str(key).lower(): str(value).strip() for key, value in metadata.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value:
            return value
    return None


def _csv_metadata(metadata: Mapping[str, str], name: str) -> list[str]:
    value = _metadata_value(metadata, name)
    return [item.strip() for item in value.split(",") if item.strip()] if value else []


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise DocumentParseError(f"invalid or unreadable PDF: {exc}") from exc


def parse_document(
    source: str,
    data: bytes,
    metadata: Mapping[str, str] | None = None,
) -> ParsedDocument:
    """Parse one UTF-8 text/Markdown/PDF object and normalize its metadata."""
    suffix = PurePosixPath(source).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise DocumentParseError(
            f"unsupported knowledge document extension {suffix!r}; "
            f"expected one of {sorted(_SUPPORTED_SUFFIXES)}"
        )
    if not data:
        raise DocumentParseError("knowledge document is empty")

    metadata = metadata or {}
    if suffix == ".pdf":
        raw_text = _extract_pdf(data)
        default_type = "pdf"
    else:
        try:
            raw_text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DocumentParseError("knowledge text must be valid UTF-8") from exc
        default_type = "markdown" if suffix in {".md", ".markdown"} else "text"

    text = normalize_text(raw_text)
    if not text:
        raise DocumentParseError("knowledge document contains no extractable text")

    title = _metadata_value(metadata, "title") or PurePosixPath(source).stem.replace("_", " ")
    language = (_metadata_value(metadata, "language") or detect_language(text)).lower()
    if language not in {"fr", "ar", "en", "multilingual", "und"}:
        raise DocumentParseError(f"unsupported language metadata: {language!r}")

    document_type = _metadata_value(metadata, "document_type") or default_type
    rich_metadata: dict[str, object] = {
        "applicable_plans": _csv_metadata(metadata, "applicable_plans"),
        "product_codes": _csv_metadata(metadata, "product_codes"),
        "regions": _csv_metadata(metadata, "regions"),
    }
    for name in ("valid_from", "valid_until"):
        value = _metadata_value(metadata, name)
        if value:
            rich_metadata[name] = value

    return ParsedDocument(
        source=source,
        title=title,
        language=language,
        document_type=document_type,
        text=text,
        checksum=sha256_hex(data),
        metadata=rich_metadata,
    )


def chunk_document(
    document: ParsedDocument,
    *,
    chunk_tokens: int = 512,
    overlap_tokens: int = 64,
) -> list[DocumentChunk]:
    """Split a document into stable overlapping passages using whitespace tokens."""
    if chunk_tokens < 1:
        raise ValueError("chunk_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be >= 0 and smaller than chunk_tokens")

    matches = list(_TOKEN.finditer(document.text))
    if not matches:
        raise DocumentParseError("knowledge document has no tokens")

    chunks: list[DocumentChunk] = []
    step = chunk_tokens - overlap_tokens
    for ordinal, start in enumerate(range(0, len(matches), step)):
        window = matches[start : start + chunk_tokens]
        if not window:
            break
        text = document.text[window[0].start() : window[-1].end()]
        chunks.append(
            DocumentChunk(
                ordinal=ordinal,
                text=text,
                token_count=len(window),
                checksum=sha256_hex(text),
                metadata=dict(document.metadata),
            )
        )
        if start + chunk_tokens >= len(matches):
            break
    return chunks
