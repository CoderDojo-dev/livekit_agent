"""Bounded, server-side health aggregation for administrator operations.

Targets come only from SERVICE_HEALTH_TARGETS. URLs, response bodies, headers and credentials
never leave this module: the serialized report carries ids, names and states only.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

_ALLOWED_STATUSES = {"reachable", "degraded", "unavailable", "unknown"}
_ALLOWED_PROBE_KINDS = {"liveness", "readiness", "none"}

_MAX_TARGETS = 32
_MAX_BODY_BYTES = 64 * 1024
_DEFAULT_TIMEOUT_MS = 1500
_DEFAULT_CACHE_TTL_MS = 15_000
_DEFAULT_CONCURRENCY = 8

_PERMITTED_PATH = "/health"


@dataclass(frozen=True)
class HealthTarget:
    id: str
    name: str
    domain: str
    probe_kind: str
    required: bool
    origin: str | None = None
    path: str | None = None

    @property
    def url(self) -> str | None:
        if self.origin is None or self.path is None:
            return None
        return f"{self.origin.rstrip('/')}{self.path}"


def _bounded_int(
    value: object,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _valid_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.query or parsed.fragment:
        return False
    if parsed.path not in {"", "/"}:
        return False

    try:
        port = parsed.port
    except ValueError:
        return False

    return port is None or 1 <= port <= 65535


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def _unknown_row(
    entry_id: str,
    name: str,
    domain: str,
    required: bool,
    reason: str = "invalid_configuration",
) -> dict[str, Any]:
    """A sanitized row for an entry that must never be probed or echoed."""
    return {
        "id": entry_id,
        "name": name,
        "domain": domain,
        "monitoring_configured": False,
        "probe_kind": "none",
        "required": required,
        "status": "unknown",
        "reason": reason,
        "latency_ms": None,
    }


def configured_targets(raw: str | None = None) -> tuple[list[HealthTarget], list[dict[str, Any]]]:
    """Parse the allow-listed target registry; invalid entries become sanitized unknown rows.

    The origin is never echoed on any error path.
    """
    value = os.getenv("SERVICE_HEALTH_TARGETS", "[]") if raw is None else raw
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], [_unknown_row("health-registry", "health-registry", "platform", True)]
    if not isinstance(items, list):
        return [], [_unknown_row("health-registry", "health-registry", "platform", True)]
    if len(items) > _MAX_TARGETS:
        return [], [_unknown_row("health-registry", "health-registry", "platform", True)]

    targets: list[HealthTarget] = []
    invalid: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            invalid.append(_unknown_row(f"target-{index + 1}", f"target-{index + 1}", "unknown", True))
            continue

        target_id = item.get("id")
        name = item.get("name")
        domain = item.get("domain")
        probe_kind = item.get("probe_kind")
        required = bool(item.get("required", True))
        origin = item.get("origin")
        path = item.get("path")

        entry_id = str(target_id) if isinstance(target_id, str) and target_id.strip() else f"target-{index + 1}"
        row_name = str(name) if isinstance(name, str) and name.strip() else entry_id
        row_domain = str(domain) if isinstance(domain, str) and domain.strip() else "unknown"

        def invalid_entry() -> dict[str, Any]:
            return _unknown_row(entry_id, row_name, row_domain, required)

        if not isinstance(probe_kind, str) or probe_kind not in _ALLOWED_PROBE_KINDS:
            invalid.append(invalid_entry())
            continue
        if entry_id in seen_ids:
            invalid.append(invalid_entry())
            continue
        if probe_kind in {"liveness", "readiness"}:
            if not isinstance(origin, str) or not _valid_origin(origin) or path != _PERMITTED_PATH:
                invalid.append(invalid_entry())
                continue
        else:
            if origin is not None and (not isinstance(origin, str) or not _valid_origin(origin)):
                invalid.append(invalid_entry())
                continue
            if path is not None and path != _PERMITTED_PATH:
                invalid.append(invalid_entry())
                continue

        seen_ids.add(entry_id)
        targets.append(
            HealthTarget(
                id=entry_id,
                name=row_name,
                domain=row_domain,
                probe_kind=probe_kind,
                required=required,
                origin=origin if isinstance(origin, str) else None,
                path=path if isinstance(path, str) else None,
            )
        )

    return targets, invalid


def _parse_payload(body: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _reported_state(payload: dict[str, Any] | None) -> tuple[str, str] | None:
    if payload is None:
        return None

    reported = str(payload.get("status", "")).lower()

    if reported in {"ok", "healthy", "ready", "reachable"}:
        return "reachable", "probe_succeeded"

    if reported in {"degraded", "warning", "partial"}:
        return "degraded", "service_reported_degraded"

    if reported in {"error", "failed", "unhealthy", "unavailable"}:
        return "unavailable", "service_reported_unavailable"

    return None


def _probe(target: HealthTarget, timeout_seconds: float) -> tuple[str, str]:
    url = target.url
    if url is None:
        return "unknown", "invalid_configuration"

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "business-api-health/1"},
    )
    try:
        with _OPENER.open(request, timeout=timeout_seconds) as response:
            code = response.status
            body = response.read(_MAX_BODY_BYTES)
    except urllib.error.HTTPError as error:
        code = error.code
        body = error.read(_MAX_BODY_BYTES)
    except TimeoutError:
        return "unavailable", "timeout"
    except (urllib.error.URLError, OSError):
        return "unavailable", "connection_failed"

    if 300 <= code < 400:
        return "unavailable", "redirect_refused"
    if code in (401, 403):
        return "unavailable", "health_auth_misconfigured"
    if code == 404:
        return "unknown", "health_contract_missing"
    if 400 <= code < 500:
        return "degraded", "http_4xx"

    payload = _parse_payload(body)
    state = _reported_state(payload)
    if state is not None:
        if code >= 500:
            if code == 503 and state == ("degraded", "service_reported_degraded"):
                return state
            return "unavailable", "http_5xx"
        return state

    if code >= 500:
        return "unavailable", "http_5xx"
    if payload is None:
        return "unknown", "invalid_response"
    return "unknown", "unrecognized_status"


async def _probe_one(
    target: HealthTarget,
    timeout_seconds: float,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    if target.probe_kind == "none":
        return {
            "id": target.id,
            "name": target.name,
            "domain": target.domain,
            "monitoring_configured": False,
            "probe_kind": "none",
            "required": target.required,
            "status": "unknown",
            "reason": "no_http_health_contract",
            "latency_ms": None,
        }

    started = time.perf_counter()

    async with semaphore:
        try:
            status, reason = await asyncio.wait_for(
                asyncio.to_thread(_probe, target, timeout_seconds),
                timeout_seconds + 0.1,
            )
        except asyncio.TimeoutError:
            status, reason = "unavailable", "timeout"

    return {
        "id": target.id,
        "name": target.name,
        "domain": target.domain,
        "monitoring_configured": True,
        "probe_kind": target.probe_kind,
        "required": target.required,
        "status": status if status in _ALLOWED_STATUSES else "unknown",
        "reason": reason,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


async def _aggregate_uncached(
    raw: str | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    targets, invalid = configured_targets(raw)

    bounded_timeout_ms = _bounded_int(
        timeout_ms if timeout_ms is not None else os.getenv("SERVICE_HEALTH_TIMEOUT_MS"),
        default=_DEFAULT_TIMEOUT_MS,
        minimum=100,
        maximum=5000,
    )
    cache_ttl_ms = _bounded_int(
        os.getenv("SERVICE_HEALTH_CACHE_TTL_MS"),
        default=_DEFAULT_CACHE_TTL_MS,
        minimum=0,
        maximum=60_000,
    )
    concurrency = _bounded_int(
        os.getenv("SERVICE_HEALTH_CONCURRENCY"),
        default=_DEFAULT_CONCURRENCY,
        minimum=1,
        maximum=16,
    )

    semaphore = asyncio.Semaphore(concurrency)
    services = list(
        await asyncio.gather(
            *(_probe_one(target, bounded_timeout_ms / 1000, semaphore) for target in targets)
        )
    )
    services.extend(invalid)

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
        "schema_version": 1,
        "overall": overall,
        "checked_at": datetime.now(UTC).isoformat(),
        "cache_ttl_ms": cache_ttl_ms,
        "probe_timeout_ms": bounded_timeout_ms,
        "business_api_liveness": {
            "status": "reachable",
            "reason": "request_served",
        },
        "services": services,
    }


_cache_lock = asyncio.Lock()
_cached_report: dict[str, Any] | None = None
_cached_until = 0.0


async def aggregate_service_health(
    raw: str | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    if raw is not None or timeout_ms is not None:
        return await _aggregate_uncached(raw=raw, timeout_ms=timeout_ms)

    global _cached_report, _cached_until

    now = time.monotonic()
    if _cached_report is not None and now < _cached_until:
        return deepcopy(_cached_report)

    async with _cache_lock:
        now = time.monotonic()
        if _cached_report is not None and now < _cached_until:
            return deepcopy(_cached_report)

        report = await _aggregate_uncached()
        ttl_ms = report["cache_ttl_ms"]

        _cached_report = deepcopy(report)
        _cached_until = time.monotonic() + ttl_ms / 1000

        return deepcopy(report)


def reset_health_cache() -> None:
    global _cached_report, _cached_until
    _cached_report = None
    _cached_until = 0.0
