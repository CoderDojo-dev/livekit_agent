"""Document parsing, metadata normalization, and deterministic chunking."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from pypdf import PdfReader

_SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}
_TOKEN_RE = re.compile(r"\S+")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_FRENCH_HINTS = {"le", "la", "les", "des", "une", "avec", "pour", "forfait"}


class DocumentParseError(RuntimeError):
    """Raised when an object cannot be converted into safe normalized text."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source: str
    title: str
    language: str
    document_type: str
    text: str
    checksum: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TextChunk:
    ordinal: int
    text: str
    token_count: int
    checksum: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise DocumentParseError("document contains no extractable text")
    return normalized


def _decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("text documents must be valid UTF-8") from exc


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise DocumentParseError(f"PDF extraction failed: {exc}") from exc
    return "\n\n".join(page for page in pages if page)


def detect_language(text: str) -> str:
    sample = text[:10_000].lower()
    if _ARABIC_RE.search(sample):
        latin = sum(char.isascii() and char.isalpha() for char in sample)
        arabic = len(_ARABIC_RE.findall(sample))
        return "multilingual" if latin > arabic // 2 else "ar"
    words = set(re.findall(r"[a-zà-ÿ]+", sample))
    return "fr" if len(words & _FRENCH_HINTS) >= 2 else "en"


def parse_document(
    key: str,
    data: bytes,
    object_metadata: dict[str, str] | None = None,
) -> ParsedDocument:
    metadata: dict[str, Any] = dict(object_metadata or {})
    suffix = PurePosixPath(key).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise DocumentParseError(
            f"unsupported document type {suffix!r}; use PDF, Markdown, or UTF-8 text"
        )

    raw_text = _extract_pdf(data) if suffix == ".pdf" else _decode_utf8(data)
    text = _normalize_text(raw_text)
    title = str(metadata.pop("title", "")).strip() or PurePosixPath(key).stem
    language = str(metadata.pop("language", "")).strip().lower() or detect_language(text)
    if language not in {"fr", "ar", "en", "multilingual", "und"}:
        raise DocumentParseError(f"unsupported language metadata: {language!r}")
    document_type = (
        str(metadata.pop("document_type", "")).strip().lower()
        or {".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".txt": "text"}[suffix]
    )

    return ParsedDocument(
        source=key,
        title=title,
        language=language,
        document_type=document_type,
        text=text,
        checksum=sha256_bytes(data),
        metadata=metadata,
    )


def chunk_document(
    text: str,
    *,
    chunk_tokens: int = 512,
    overlap_tokens: int = 64,
) -> list[TextChunk]:
    """Split normalized text into deterministic overlapping whitespace-token passages."""
    if chunk_tokens < 32:
        raise ValueError("chunk_tokens must be at least 32")
    if overlap_tokens < 0 or overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be >= 0 and smaller than chunk_tokens")

    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        raise DocumentParseError("document contains no tokens")
    step = chunk_tokens - overlap_tokens
    chunks: list[TextChunk] = []
    for ordinal, start in enumerate(range(0, len(tokens), step)):
        window = tokens[start : start + chunk_tokens]
        if not window:
            break
        chunk_text = " ".join(window)
        chunks.append(
            TextChunk(
                ordinal=ordinal,
                text=chunk_text,
                token_count=len(window),
                checksum=sha256_text(chunk_text),
            )
        )
        if start + chunk_tokens >= len(tokens):
            break
    return chunks
