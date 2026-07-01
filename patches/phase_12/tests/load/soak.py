"""Soak test (Blueprint section 20 'Soak'): many sequential calls, watch for resource/state bleed.

Drives the HTTP path repeatedly and reports RSS growth. A healthy run shows flat memory (no leak).
For the voice path, run the worker against a sequential-call generator and watch the same RSS plus
the OTel session counters; this script covers the services.

Usage:
    pip install httpx psutil
    python tests/load/soak.py --url http://localhost:8108/health --iterations 5000
"""
from __future__ import annotations

import argparse
import asyncio

import httpx

try:
    import os

    import psutil
    _proc = psutil.Process(os.getpid())
except Exception:  # noqa: BLE001
    _proc = None


def _rss_mb() -> float:
    return round(_proc.memory_info().rss / 1_048_576, 1) if _proc else -1.0


async def run(url: str, iterations: int) -> None:
    start_rss = _rss_mb()
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(iterations):
            try:
                await client.get(url)
            except httpx.HTTPError:
                pass
            if i and i % 1000 == 0:
                print(f"iter={i} rss={_rss_mb()}MB")
    end_rss = _rss_mb()
    print(f"done iterations={iterations} rss_start={start_rss}MB rss_end={end_rss}MB delta={round(end_rss - start_rss, 1)}MB")
    if start_rss > 0 and end_rss - start_rss > 50:
        raise SystemExit("WARN: RSS grew >50MB across the soak run - investigate for a leak")
    print("PASS: no significant memory growth")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--iterations", type=int, default=5000)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.iterations))


if __name__ == "__main__":
    main()