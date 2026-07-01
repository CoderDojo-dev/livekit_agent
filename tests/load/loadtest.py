"""Lightweight load test against the HTTP services (Blueprint section 20 'Load').

Measures p50/p95 latency against a budget. The voice TTFA budget is asserted separately via the
OTel `telecom.agent.ttfa.seconds` histogram (Phase 11) under a real concurrent-call run; this script
covers the request/response services (business-api, context-service, token-service).

Usage:
    pip install httpx
    python tests/load/loadtest.py --url http://localhost:8108/health --requests 500 --concurrency 25 --budget-ms 250
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def _worker(client: httpx.AsyncClient, url: str, queue: asyncio.Queue, latencies: list[float]) -> None:
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        start = time.perf_counter()
        try:
            await client.get(url)
        except httpx.HTTPError:
            pass
        latencies.append((time.perf_counter() - start) * 1000.0)
        queue.task_done()


async def run(url: str, total: int, concurrency: int) -> list[float]:
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(total):
        queue.put_nowait(1)
    latencies: list[float] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        await asyncio.gather(*[_worker(client, url, queue, latencies) for _ in range(concurrency)])
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--budget-ms", type=float, default=250.0)
    args = parser.parse_args()

    latencies = asyncio.run(run(args.url, args.requests, args.concurrency))
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"requests={len(latencies)} p50={p50:.1f}ms p95={p95:.1f}ms budget={args.budget_ms:.0f}ms")
    if p95 > args.budget_ms:
        raise SystemExit(f"FAIL: p95 {p95:.1f}ms exceeds budget {args.budget_ms:.0f}ms")
    print("PASS: within latency budget")


if __name__ == "__main__":
    main()