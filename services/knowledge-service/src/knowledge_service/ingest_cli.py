"""Command line entrypoint for on-demand knowledge ingestion."""
from __future__ import annotations

import argparse
import json
import sys

from knowledge_service.ingestion import KnowledgeIngestor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest MinIO knowledge objects")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--object", help="one object key in telecom-knowledge")
    target.add_argument("--all", action="store_true", help="ingest every supported object")
    parser.add_argument("--prefix", default="", help="optional key prefix used with --all")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ingestor = KnowledgeIngestor.from_env()
    failures = 0
    try:
        keys = [args.object] if args.object else ingestor.store.list_keys(args.prefix)
        keys = [
            key for key in keys if key and key.lower().endswith((".pdf", ".md", ".markdown", ".txt"))
        ]
        if not keys:
            raise SystemExit("FAIL: no supported knowledge objects found")
        for key in keys:
            try:
                result = ingestor.ingest(key)
                print(json.dumps(result.__dict__, sort_keys=True))
            except Exception as exc:
                failures += 1
                print(f"FAIL: {key}: {exc}", file=sys.stderr)
    finally:
        ingestor.close()
    if failures:
        raise SystemExit(f"FAIL: {failures} object(s) failed ingestion")
    print("KNOWLEDGE_INGESTION_PASSED")


if __name__ == "__main__":
    main()
