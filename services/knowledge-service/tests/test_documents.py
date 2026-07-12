"""Offline parser and deterministic chunker tests."""
from __future__ import annotations

import pytest

from knowledge_service.documents import (
    DocumentParseError,
    chunk_document,
    parse_document,
)


def test_markdown_parser_normalizes_metadata_and_utf8() -> None:
    parsed = parse_document(
        "plans/flexi.md",
        "# Offre Flexi\r\n\r\nLe forfait mobile avec internet.".encode(),
        {"title": "Flexi", "language": "fr", "document_type": "product"},
    )
    assert parsed.title == "Flexi"
    assert parsed.language == "fr"
    assert parsed.document_type == "product"
    assert "\r" not in parsed.text
    assert len(parsed.checksum) == 64


def test_invalid_utf8_fails_closed() -> None:
    with pytest.raises(DocumentParseError, match="UTF-8"):
        parse_document("bad.txt", b"\xff\xfe")


def test_chunker_is_overlapping_and_deterministic() -> None:
    text = " ".join(f"token-{index}" for index in range(100))
    first = chunk_document(text, chunk_tokens=40, overlap_tokens=10)
    second = chunk_document(text, chunk_tokens=40, overlap_tokens=10)
    assert first == second
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert first[0].text.split()[-10:] == first[1].text.split()[:10]
    assert all(len(chunk.checksum) == 64 for chunk in first)
