#!/usr/bin/env python3
"""Probe every service /health and report (diagnostic #9). Exit non-zero if any are down."""
from __future__ import annotations

import sys
import urllib.request

SERVICES = {
    "context-service": 8101, "knowledge-service": 8102, "decision-service": 8103,
    "policy-service": 8104, "execution-service": 8105, "notification-service": 8106,
    "token-service": 8107, "business-api": 8108,
}


def _up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    all_ok = True
    for name, port in SERVICES.items():
        ok = _up(port)
        all_ok = all_ok and ok
        print(f"[{'OK  ' if ok else 'DOWN'}] {name:<22} :{port}")
    print("\nAll services healthy." if all_ok else "\nSome services are DOWN — check their terminals/logs.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())