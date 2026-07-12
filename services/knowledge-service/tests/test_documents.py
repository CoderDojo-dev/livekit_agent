"""Offline tests for parsing and deterministic chunking."""
from __future__ import annotations

import pytest

from knowledge_service.documents import (
    DocumentParseError,
    chunk_document,
    parse_document,
)


def test_parse_markdown_normalizes_metadata_and_utf8() -> None:
    document = parse_document(
        "plans/flexi.md",
        "# Offre Flexi\r\n\r\nLe forfait mobile est disponible.\n".encode(),
        {
            "x-amz-meta-title": "Offre Flexi",
            "x-amz-meta-language": "fr",
            "x-amz-meta-document-type": "product-guide",
            "x-amz-meta-applicable-plans": "flexi, premium",
            "x-amz-meta-product-codes": "FX1, FX2",
            "x-amz-meta-region": "tn",
            "x-amz-meta-valid-from": "2026-01-01",
        },
    )

    assert document.title == "Offre Flexi"
    assert document.language == "fr"
    assert document.document_type == "product-guide"
    assert document.metadata["applicable_plans"] == ["flexi", "premium"]
    assert document.metadata["product_codes"] == ["FX1", "FX2"]
    assert "\r" not in document.text
    assert len(document.checksum) == 64


def test_chunking_is_overlapping_sequential_and_deterministic() -> None:
    text = " ".join(f"token-{index}" for index in range(20))
    document = parse_document("guide.txt", text.encode(), {"language": "en"})

    first = chunk_document(document, chunk_tokens=8, overlap_tokens=2)
    second = chunk_document(document, chunk_tokens=8, overlap_tokens=2)

    assert [chunk.ordinal for chunk in first] == [0, 1, 2]
    assert [chunk.token_count for chunk in first] == [8, 8, 8]
    assert first[0].text.split()[-2:] == first[1].text.split()[:2]
    assert [chunk.checksum for chunk in first] == [chunk.checksum for chunk in second]


def test_parser_rejects_invalid_utf8_and_unknown_extensions() -> None:
    with pytest.raises(DocumentParseError, match="valid UTF-8"):
        parse_document("bad.txt", b"\xff")
    with pytest.raises(DocumentParseError, match="unsupported"):
        parse_document("bad.docx", b"content")
