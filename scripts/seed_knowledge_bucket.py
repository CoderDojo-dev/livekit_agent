"""Publish the built-in corpus into the MinIO knowledge bucket (RAG phase 3).

The corpus already exists in code (`knowledge_service.corpus.CORPUS`) but is unreachable by the
vector pipeline, which reads from MinIO. This lifts it into the bucket as front-mattered
Markdown so `knowledge-ingest` has real documents to chunk, embed, and index on day one.

Idempotent: writing identical bytes leaves the ingestion checksum unchanged, so re-running this
and re-ingesting is a no-op rather than a re-embed.

Usage (inside the knowledge-service container):
    python /app/scripts/seed_knowledge_bucket.py
"""
from __future__ import annotations

import logging

from knowledge_service.corpus import CORPUS
from knowledge_service.minio_store import get_knowledge_store


def as_markdown(document) -> bytes:
    """Render one corpus document as front-mattered Markdown."""
    lines = [
        "---",
        f"title: {document.title}",
        "language: en",
        f"document_type: {document.source.split('/')[0] if '/' in document.source else 'general'}",
        "---",
        "",
        f"# {document.title}",
        "",
        document.text.strip(),
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    store = get_knowledge_store()
    written = 0
    for document in CORPUS:
        key = f"{document.source}.md" if not document.source.endswith(".md") else document.source
        store.put(key, as_markdown(document), content_type="text/markdown")
        print(f"  put {key}")
        written += 1
    print(f"BUCKET={store.bucket} OBJECTS_WRITTEN={written}")
    print("KNOWLEDGE_SEED_OK")


if __name__ == "__main__":
    main()
