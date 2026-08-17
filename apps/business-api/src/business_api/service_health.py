"""Bounded, server-side health aggregation for administrator operations.

Targets come only from SERVICE_HEALTH_TARGETS. URLs and response bodies never leave this module.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_STATUSES = {"reachable", "degraded", "unavailable", "unknown"}


@dataclass(frozen=True)
class HealthTarget:
    name: str
    domain: str
    url: str
    required: bool = True


def configured_targets(raw: str | None = None) -> tuple[list[HealthTarget], list[dict[str, Any]]]:
    """Parse the allow-listed target registry; invalid entries remain visible as unknown."""
    value = os.getenv("SERVICE_HEALTH_TARGETS", "[]") if raw is None else raw
    invalid: list[dict[str, Any]] = []
    try:
        items = json.loads(value)
        if not isinstance(items, list):
            raise ValueError("registry must be a JSON array")
    except (json.JSONDecodeError, ValueError):
        return [], [{"name": "health-registry", "domain": "platform", "required": True}]

    targets: list[HealthTarget] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            invalid.append({"name": f"target-{index + 1}", "domain": "unknown", "required": True})
            continue
        name, domain, url = item.get("name"), item.get("domain"), item.get("url")
        if not all(isinstance(v, str) and v.strip() for v in (name, domain, url)) or not url.startswith(("http://", "https://")):
            invalid.append({"name": str(name or f"target-{index + 1}"), "domain": str(domain or "unknown"), "required": bool(item.get("required", True))})
            continue
        targets.append(HealthTarget(name.strip(), domain.strip(), url.strip(), bool(item.get("required", True))))
    return targets, invalid


def _probe(target: HealthTarget, timeout_seconds: float) -> tuple[str, str]:
    request = urllib.request.Request(target.url, headers={"Accept": "application/json", "User-Agent": "business-api-health/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            code = response.status
            body = response.read(65536)
    except urllib.error.HTTPError as error:
        return ("degraded" if 400 <= error.code < 500 else "unavailable", f"http_{error.code}")
    except TimeoutError:
        return "unavailable", "timeout"
    except (urllib.error.URLError, OSError):
        return "unavailable", "connection_failed"

    if not 200 <= code < 300:
        return "unavailable", f"http_{code}"
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "unknown", "invalid_response"
    if not isinstance(payload, dict):
        return "unknown", "invalid_response"
    reported = str(payload.get("status", "")).lower()
    if reported in {"ok", "healthy", "ready", "reachable"}:
        return "reachable", "probe_succeeded"
    if reported in {"degraded", "warning", "partial"}:
        return "degraded", "service_reported_degraded"
    if reported in {"error", "failed", "unhealthy", "unavailable"}:
        return "unavailable", "service_reported_unavailable"
    return "unknown", "unrecognized_status"


async def _probe_one(target: HealthTarget, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        status, reason = await asyncio.wait_for(asyncio.to_thread(_probe, target, timeout_seconds), timeout_seconds + 0.1)
    except asyncio.TimeoutError:
        status, reason = "unavailable", "timeout"
    return {
        "name": target.name, "domain": target.domain, "configured": True,
        "required": target.required, "status": status if status in _STATUSES else "unknown",
        "reason": reason, "latency_ms": round((time.perf_counter() - started) * 1000),
    }


async def aggregate_service_health(raw: str | None = None, timeout_ms: int | None = None) -> dict[str, Any]:
    targets, invalid = configured_targets(raw)
    bounded_ms = max(100, min(timeout_ms or int(os.getenv("SERVICE_HEALTH_TIMEOUT_MS", "1500")), 5000))
    services = list(await asyncio.gather(*(_probe_one(target, bounded_ms / 1000) for target in targets)))
    services.extend({**item, "configured": False, "status": "unknown", "reason": "invalid_configuration", "latency_ms": None} for item in invalid)
    required = [item for item in services if item["required"]]
    states = {item["status"] for item in required}
    if not services:
        overall = "unknown"
    elif "unavailable" in states:
        overall = "unavailable"
    elif "degraded" in states or "unknown" in states:
        overall = "degraded"
    else:
        overall = "reachable"
    return {
        "schema_version": 1, "overall": overall,
        "checked_at": datetime.now(UTC).isoformat(), "timeout_ms": bounded_ms,
        "services": services,
    }
