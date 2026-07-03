#!/usr/bin/env python3
"""Probe service health and report. Exit non-zero if any service is down."""
from __future__ import annotations

import socket
import sys
import urllib.request

HTTP_SERVICES = {
    "context-service": 8101,
    "knowledge-service": 8102,
    "decision-service": 8103,
    "policy-service": 8104,
    "execution-service": 8105,
    "notification-service": 8106,
    "token-service": 8107,
    "business-api": 8108,
}

TCP_SERVICES = {
    "ai-knowledge-rag": 8201,
    "ticketing-glpi": 8202,
    "messaging-gateway": 8203,
}


def _http_up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _tcp_up(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=3):
            return True
    except Exception:
        return False


def main() -> int:
    all_ok = True
    for name, port in HTTP_SERVICES.items():
        ok = _http_up(port)
        all_ok = all_ok and ok
        print(f"[{'OK  ' if ok else 'DOWN'}] {name:<22} :{port}")
    for name, port in TCP_SERVICES.items():
        ok = _tcp_up(port)
        all_ok = all_ok and ok
        print(f"[{'OK  ' if ok else 'DOWN'}] {name:<22} :{port}")
    print("\nAll services healthy." if all_ok else "\nSome services are DOWN - check their terminals/logs.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
