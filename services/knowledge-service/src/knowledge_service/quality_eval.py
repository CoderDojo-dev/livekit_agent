"""Executable retrieval quality, isolation, and latency gate."""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class QualityGateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LatencyReport:
    samples_ms: tuple[float, ...]
    p50_ms: float
    p95_ms: float


def percentile(samples: list[float], percentile_value: float) -> float:
    if not samples:
        raise ValueError("latency samples are required")
    ordered = sorted(samples)
    rank = max(1, math.ceil(percentile_value * len(ordered)))
    return ordered[rank - 1]


def run_suite(
    *,
    service_url: str,
    cases_path: Path,
    repeats: int,
    p95_limit_ms: float,
) -> LatencyReport:
    cases = json.loads(cases_path.read_text())
    if not isinstance(cases, list) or not cases:
        raise QualityGateError("quality suite must contain at least one case")
    api_key = os.getenv("INTERNAL_API_KEY", "")
    headers = {"X-API-Key": api_key} if api_key else {}
    samples: list[float] = []

    with httpx.Client(timeout=60.0, headers=headers) as client:
        for case in cases:
            request = dict(case["request"])
            expected_sources = set(case.get("expected_sources", []))
            forbidden_sources = set(case.get("forbidden_sources", []))
            for iteration in range(repeats):
                started = time.perf_counter()
                response = client.post(f"{service_url.rstrip('/')}/search", json=request)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                response.raise_for_status()
                samples.append(elapsed_ms)
                passages = response.json().get("passages") or []
                sources = {item.get("source") for item in passages}
                if not expected_sources.issubset(sources):
                    raise QualityGateError(
                        f"{case['name']} missed expected sources: "
                        f"{sorted(expected_sources - sources)}"
                    )
                leaked = forbidden_sources & sources
                if leaked:
                    raise QualityGateError(
                        f"{case['name']} leaked forbidden sources: {sorted(leaked)}"
                    )
                if iteration == 0:
                    print(f"QUALITY_CASE_PASSED={case['name']}")

    report = LatencyReport(
        samples_ms=tuple(samples),
        p50_ms=statistics.median(samples),
        p95_ms=percentile(samples, 0.95),
    )
    print(f"RAG_LATENCY_SAMPLES={len(samples)}")
    print(f"RAG_LATENCY_P50_MS={report.p50_ms:.2f}")
    print(f"RAG_LATENCY_P95_MS={report.p95_ms:.2f}")
    if report.p95_ms >= p95_limit_ms:
        raise QualityGateError(
            f"p95 latency {report.p95_ms:.2f}ms exceeds {p95_limit_ms:.2f}ms"
        )
    print("RAG_RETRIEVAL_QUALITY_PASSED")
    print("RAG_LATENCY_GATE_PASSED")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run production RAG quality gates")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("scripts/rag_quality_cases.json"),
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--p95-ms", type=float, default=500.0)
    parser.add_argument(
        "--service-url",
        default=os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8102"),
    )
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("FAIL: repeats must be positive")
    run_suite(
        service_url=args.service_url,
        cases_path=args.cases,
        repeats=args.repeats,
        p95_limit_ms=args.p95_ms,
    )


if __name__ == "__main__":
    main()
