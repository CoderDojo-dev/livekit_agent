from __future__ import annotations

import asyncio
import json
import time

import pytest

from business_api import service_health


def registry(*items):
    return json.dumps(items)


def test_empty_registry_is_truthfully_unknown():
    result = asyncio.run(service_health.aggregate_service_health("[]", 100))
    assert result["overall"] == "unknown"
    assert result["services"] == []


def test_invalid_registry_is_visible_without_echoing_url():
    result = asyncio.run(service_health.aggregate_service_health("not-json", 100))
    assert result["overall"] == "degraded"
    assert result["services"][0]["configured"] is False
    assert "url" not in result["services"][0]


def test_parallel_aggregation_and_status_precedence(monkeypatch: pytest.MonkeyPatch):
    def fake_probe(target, timeout):
        time.sleep(0.05)
        return ("reachable", "probe_succeeded") if target.name == "a" else ("unavailable", "timeout")

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    started = time.perf_counter()
    result = asyncio.run(service_health.aggregate_service_health(registry(
        {"name": "a", "domain": "core", "url": "http://a/health"},
        {"name": "b", "domain": "core", "url": "http://b/health"},
    ), 100))
    assert time.perf_counter() - started < 0.095
    assert result["overall"] == "unavailable"
    assert [item["status"] for item in result["services"]] == ["reachable", "unavailable"]
    assert all("url" not in item for item in result["services"])


def test_optional_failure_does_not_reduce_overall(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service_health, "_probe", lambda target, timeout: ("unavailable", "connection_failed") if not target.required else ("reachable", "probe_succeeded"))
    result = asyncio.run(service_health.aggregate_service_health(registry(
        {"name": "required", "domain": "core", "url": "http://required/health"},
        {"name": "optional", "domain": "edge", "url": "http://optional/health", "required": False},
    ), 100))
    assert result["overall"] == "reachable"


def test_timeout_budget_is_clamped_and_forwarded(monkeypatch: pytest.MonkeyPatch):
    observed = []
    def probe(target, timeout):
        observed.append(timeout)
        return "unavailable", "timeout"
    monkeypatch.setattr(service_health, "_probe", probe)
    result = asyncio.run(service_health.aggregate_service_health(registry(
        {"name": "slow", "domain": "core", "url": "http://slow/health"},
    ), 1))
    assert result["timeout_ms"] == 100
    assert observed == [0.1]
    assert result["services"][0]["status"] == "unavailable"
    assert result["services"][0]["reason"] == "timeout"
