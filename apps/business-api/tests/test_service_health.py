"""Unit tests for the bounded service-health aggregator (cookbook 2).

Covers registry validation, per-status HTTP mapping against real local servers,
concurrency bounding, cache semantics and full redaction of the report payload.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from business_api import service_health


def registry(*items) -> str:
    return json.dumps(list(items))


def _run(coro) -> dict:
    return asyncio.run(coro)


def _serve(handler_cls) -> tuple[HTTPServer, threading.Thread, int]:
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


class _JsonHandler(BaseHTTPRequestHandler):
    """Serves a canned JSON body with a canned status code; no logging."""

    status = 200
    body = b'{"status":"ok"}'

    def do_GET(self):
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


class _SlowHandler(_JsonHandler):
    def do_GET(self):
        time.sleep(1.0)
        super().do_GET()


@pytest.fixture(autouse=True)
def _fresh_cache():
    service_health.reset_health_cache()
    yield
    service_health.reset_health_cache()


# ---- 1. registry validation ---------------------------------------------------

def test_empty_registry_is_truthfully_unknown():
    result = _run(service_health.aggregate_service_health("[]", 100))
    assert result["overall"] == "unknown"
    assert result["services"] == []


def test_non_json_registry_yields_sanitized_health_registry_row():
    result = _run(service_health.aggregate_service_health("not-json", 100))
    row = result["services"][0]
    assert row["id"] == "health-registry"
    assert row["status"] == "unknown"
    assert row["reason"] == "invalid_configuration"
    assert row["monitoring_configured"] is False


def test_non_array_registry_yields_health_registry_row():
    result = _run(service_health.aggregate_service_health('{"name":"x"}', 100))
    assert result["services"][0]["reason"] == "invalid_configuration"


def test_oversized_registry_is_rejected():
    too_many = [{"id": f"t{i}", "name": f"t{i}", "domain": "d", "probe_kind": "none"} for i in range(33)]
    result = _run(service_health.aggregate_service_health(json.dumps(too_many), 100))
    assert result["services"][0]["id"] == "health-registry"
    assert len(result["services"]) == 1


def test_missing_id_gets_stable_placeholder_id():
    result = _run(service_health.aggregate_service_health(
        registry({"name": "no-id", "domain": "d", "probe_kind": "none"}), 100))
    assert result["services"][0]["id"] == "target-1"


def test_missing_name_and_domain_are_sanitized():
    result = _run(service_health.aggregate_service_health(
        registry({"id": "x", "probe_kind": "none"}), 100))
    row = result["services"][0]
    assert row["name"] == "x"
    assert row["domain"] == "unknown"


def test_unknown_probe_kind_is_invalid_and_never_probed(monkeypatch):
    def fail_if_probed(target, timeout):
        raise AssertionError("invalid target must never be probed")
    monkeypatch.setattr(service_health, "_probe", fail_if_probed)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "x", "name": "x", "domain": "d",
                  "origin":"http://x", "path": "/health",
                  "probe_kind": "mystery", "required": True}), 100))
    row = result["services"][0]
    assert row["status"] == "unknown"
    assert row["reason"] == "invalid_configuration"
    assert row["monitoring_configured"] is False


def test_duplicate_ids_second_is_invalid(monkeypatch):
    def fail_if_probed(target, timeout):
        raise AssertionError("duplicate must never be probed")
    monkeypatch.setattr(service_health, "_probe", fail_if_probed)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "dup", "name": "a", "domain": "d", "probe_kind": "none"},
                 {"id": "dup", "name": "b", "domain": "d", "probe_kind": "none"}), 100))
    assert result["services"][0]["name"] == "a"
    assert result["services"][1]["reason"] == "invalid_configuration"


@pytest.mark.parametrize("origin", [
    "ftp://x/health",
    "http://user:pass@x/health",
    "http://x/health?q=1",
    "http://x/health#frag",
    "http://x/extra/path",
    "http://x:99999/health",
])
def test_forbidden_origins_are_invalid(monkeypatch, origin):
    def fail_if_probed(target, timeout):
        raise AssertionError("invalid origin must never be probed")
    monkeypatch.setattr(service_health, "_probe", fail_if_probed)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "x", "name": "x", "domain": "d", "origin": origin,
                  "path": "/health", "probe_kind": "liveness"}), 100))
    assert result["services"][0]["reason"] == "invalid_configuration"


def test_non_health_path_is_invalid():
    result = _run(service_health.aggregate_service_health(
        registry({"id": "x", "name": "x", "domain": "d", "origin": "http://x:8101",
                  "path": "/metrics", "probe_kind": "liveness"}), 100))
    assert result["services"][0]["reason"] == "invalid_configuration"


def test_none_kind_with_valid_origin_is_accepted_but_not_probed(monkeypatch):
    def fail_if_probed(target, timeout):
        raise AssertionError("none-kind must never be probed")
    monkeypatch.setattr(service_health, "_probe", fail_if_probed)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "w", "name": "w", "domain": "d", "origin": "http://w:8200",
                  "probe_kind": "none", "required": True}), 100))
    row = result["services"][0]
    assert row["status"] == "unknown"
    assert row["reason"] == "no_http_health_contract"
    assert row["monitoring_configured"] is False


# ---- 2. HTTP mapping (real servers) -------------------------------------------

def test_healthy_json_is_reachable():
    server, thread, port = _serve(_JsonHandler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        assert result["services"][0]["status"] == "reachable"
        assert result["services"][0]["reason"] == "probe_succeeded"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.parametrize("status,expected_reason", [
    (503, "service_reported_degraded"),
    (418, "http_4xx"),
    (404, "health_contract_missing"),
    (401, "health_auth_misconfigured"),
    (403, "health_auth_misconfigured"),
])
def test_degraded_body_on_503_is_degraded_only_for_503(monkeypatch, status, expected_reason):
    Handler = type("Handler", (_JsonHandler,), {"status": status, "body": b'{"status":"degraded"}'})
    server, thread, port = _serve(Handler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        row = result["services"][0]
        if status == 503:
            assert row["status"] == "degraded"
            assert row["reason"] == expected_reason
        else:
            assert row["reason"] == expected_reason
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_500_with_ok_body_is_still_http_5xx():
    class Handler(_JsonHandler):
        status = 500
        body = b'{"status":"ok"}'
    server, thread, port = _serve(Handler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        row = result["services"][0]
        assert row["status"] == "unavailable"
        assert row["reason"] == "http_5xx"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_redirect_is_refused_not_followed():
    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "/other")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass
    server, thread, port = _serve(RedirectHandler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        row = result["services"][0]
        assert row["status"] == "unavailable"
        assert row["reason"] == "redirect_refused"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_timeout_is_unavailable_timeout():
    server, thread, port = _serve(_SlowHandler)
    try:
        started = time.perf_counter()
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        assert time.perf_counter() - started < 0.9
        row = result["services"][0]
        assert row["status"] == "unavailable"
        assert row["reason"] == "timeout"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_connection_failure_is_unavailable():
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d",
                  "origin": "http://127.0.0.1:1", "path": "/health",
                  "probe_kind": "liveness"}), 100))
    row = result["services"][0]
    assert row["status"] == "unavailable"
    assert row["reason"] == "connection_failed"


@pytest.mark.parametrize("payload,expected", [
    (b'{"status":"ok"}', ("reachable", "probe_succeeded")),
    (b'{"status":"healthy"}', ("reachable", "probe_succeeded")),
    (b'{"status":"ready"}', ("reachable", "probe_succeeded")),
    (b'{"status":"degraded"}', ("degraded", "service_reported_degraded")),
    (b'{"status":"warning"}', ("degraded", "service_reported_degraded")),
    (b'{"status":"error"}', ("unavailable", "service_reported_unavailable")),
    (b'{"status":"unhealthy"}', ("unavailable", "service_reported_unavailable")),
    (b'not-json', ("unknown", "invalid_response")),
    (b'[1,2]', ("unknown", "invalid_response")),
    (b'{"status":"weird"}', ("unknown", "unrecognized_status")),
    (b'{}', ("unknown", "unrecognized_status")),
])
def test_reported_status_mapping(payload, expected):
    class Handler(_JsonHandler):
        body = payload
    server, thread, port = _serve(Handler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        row = result["services"][0]
        assert (row["status"], row["reason"]) == expected
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---- 3. aggregation, precedence and bounding -----------------------------------

def test_concurrency_is_capped(monkeypatch):
    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_probe(target, timeout):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_CONCURRENCY", "1")
    items = [{"id": f"t{i}", "name": f"t{i}", "domain": "d",
              "origin":"http://t", "path": "/health", "probe_kind": "liveness"}
             for i in range(8)]
    result = _run(service_health.aggregate_service_health(registry(*items), 100))
    assert peak == 1
    assert all(item["status"] == "reachable" for item in result["services"])


def test_parallel_aggregation_is_bounded_by_wall_time(monkeypatch):
    def fake_probe(target, timeout):
        time.sleep(0.05)
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    started = time.perf_counter()
    result = _run(service_health.aggregate_service_health(registry(
        {"id": "a", "name": "a", "domain": "core", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"},
        {"id": "b", "name": "b", "domain": "core", "origin":"http://b",
         "path": "/health", "probe_kind": "liveness"},
    ), 100))
    assert time.perf_counter() - started < 0.095
    assert [item["status"] for item in result["services"]] == ["reachable", "reachable"]


def test_timeout_budget_is_clamped_and_forwarded(monkeypatch):
    observed = []

    def probe(target, timeout):
        observed.append(timeout)
        return "unavailable", "timeout"

    monkeypatch.setattr(service_health, "_probe", probe)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d", "origin":"http://s",
                  "path": "/health", "probe_kind": "liveness"}), 1))
    assert result["probe_timeout_ms"] == 100
    assert observed == [0.1]
    assert result["services"][0]["status"] == "unavailable"
    assert result["services"][0]["reason"] == "timeout"


def test_timeout_budget_caps_at_5000(monkeypatch):
    observed = []

    def probe(target, timeout):
        observed.append(timeout)
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", probe)
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d", "origin":"http://s",
                  "path": "/health", "probe_kind": "liveness"}), 99999))
    assert result["probe_timeout_ms"] == 5000
    assert observed == [5.0]


def test_invalid_env_ints_never_500(monkeypatch):
    monkeypatch.setenv("SERVICE_HEALTH_TIMEOUT_MS", "garbage")
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "garbage")
    monkeypatch.setenv("SERVICE_HEALTH_CONCURRENCY", "garbage")
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d", "probe_kind": "none"}), None))
    assert result["probe_timeout_ms"] == 1500
    assert result["cache_ttl_ms"] == 15000


def test_env_tuning_is_clamped(monkeypatch):
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "99999")
    monkeypatch.setenv("SERVICE_HEALTH_CONCURRENCY", "99")
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d", "probe_kind": "none"}), None))
    assert result["cache_ttl_ms"] == 60000
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "-5")
    monkeypatch.setenv("SERVICE_HEALTH_CONCURRENCY", "0")
    result = _run(service_health.aggregate_service_health(
        registry({"id": "s", "name": "s", "domain": "d", "probe_kind": "none"}), None))
    assert result["cache_ttl_ms"] == 0
    assert result["services"][0]["status"] == "unknown"


def test_overall_precedence_required_unavailable_wins(monkeypatch):
    monkeypatch.setattr(service_health, "_probe",
                        lambda target, timeout: ("degraded", "service_reported_degraded")
                        if target.id == "a" else ("unavailable", "timeout"))
    result = _run(service_health.aggregate_service_health(registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"},
        {"id": "b", "name": "b", "domain": "d", "origin":"http://b",
         "path": "/health", "probe_kind": "liveness"},
    ), 100))
    assert result["overall"] == "unavailable"


def test_overall_required_unknown_produces_degraded(monkeypatch):
    monkeypatch.setattr(service_health, "_probe",
                        lambda target, timeout: ("reachable", "probe_succeeded")
                        if target.id == "a" else ("unknown", "no_http_health_contract"))
    result = _run(service_health.aggregate_service_health(registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"},
        {"id": "b", "name": "b", "domain": "d", "origin":"http://b",
         "path": "/health", "probe_kind": "liveness"},
    ), 100))
    assert result["overall"] == "degraded"


def test_optional_failure_does_not_reduce_overall(monkeypatch):
    monkeypatch.setattr(service_health, "_probe",
                        lambda target, timeout: ("unavailable", "connection_failed")
                        if not target.required else ("reachable", "probe_succeeded"))
    result = _run(service_health.aggregate_service_health(registry(
        {"id": "req", "name": "req", "domain": "core", "origin":"http://req",
         "path": "/health", "probe_kind": "liveness"},
        {"id": "opt", "name": "opt", "domain": "edge", "origin":"http://opt",
         "path": "/health", "probe_kind": "liveness", "required": False},
    ), 100))
    assert result["overall"] == "reachable"
    assert result["services"][1]["status"] == "unavailable"


def test_all_required_reachable_is_reachable(monkeypatch):
    monkeypatch.setattr(service_health, "_probe",
                        lambda target, timeout: ("reachable", "probe_succeeded"))
    result = _run(service_health.aggregate_service_health(registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"},
        {"id": "b", "name": "b", "domain": "d", "origin":"http://b",
         "path": "/health", "probe_kind": "liveness"},
    ), 100))
    assert result["overall"] == "reachable"


# ---- 4. cache and single-flight -------------------------------------------------

def test_cache_serves_same_snapshot_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_probe(target, timeout):
        calls["n"] += 1
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_TARGETS", registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"}))
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "60000")
    first = _run(service_health.aggregate_service_health())
    second = _run(service_health.aggregate_service_health())
    assert first["checked_at"] == second["checked_at"]
    assert calls["n"] == 1


def test_cache_expires_and_advances(monkeypatch):
    calls = {"n": 0}

    def fake_probe(target, timeout):
        calls["n"] += 1
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_TARGETS", registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"}))
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "0")
    first = _run(service_health.aggregate_service_health())
    time.sleep(0.002)
    second = _run(service_health.aggregate_service_health())
    assert first["checked_at"] != second["checked_at"]
    assert calls["n"] == 2


def test_single_flight_for_concurrent_callers(monkeypatch):
    calls = {"n": 0}
    lock = threading.Lock()

    def fake_probe(target, timeout):
        with lock:
            calls["n"] += 1
        time.sleep(0.05)
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_TARGETS", registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"}))
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "60000")
    async def _two():
        return await asyncio.gather(
            service_health.aggregate_service_health(),
            service_health.aggregate_service_health(),
        )
    first, second = _run(_two())
    assert calls["n"] == 1
    assert first["checked_at"] == second["checked_at"]


def test_explicit_raw_bypasses_cache(monkeypatch):
    calls = {"n": 0}

    def fake_probe(target, timeout):
        calls["n"] += 1
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "60000")
    raw = registry({"id": "a", "name": "a", "domain": "d", "origin":"http://a",
                    "path": "/health", "probe_kind": "liveness"})
    first = _run(service_health.aggregate_service_health(raw, 100))
    second = _run(service_health.aggregate_service_health(raw, 100))
    assert calls["n"] == 2


def test_reset_health_cache_forces_refresh(monkeypatch):
    calls = {"n": 0}

    def fake_probe(target, timeout):
        calls["n"] += 1
        return "reachable", "probe_succeeded"

    monkeypatch.setattr(service_health, "_probe", fake_probe)
    monkeypatch.setenv("SERVICE_HEALTH_TARGETS", registry(
        {"id": "a", "name": "a", "domain": "d", "origin":"http://a",
         "path": "/health", "probe_kind": "liveness"}))
    monkeypatch.setenv("SERVICE_HEALTH_CACHE_TTL_MS", "60000")
    _run(service_health.aggregate_service_health())
    service_health.reset_health_cache()
    _run(service_health.aggregate_service_health())
    assert calls["n"] == 2


# ---- 5. contract shape and redaction -------------------------------------------

def test_contract_fields_are_complete(monkeypatch):
    monkeypatch.setattr(service_health, "_probe",
                        lambda target, timeout: ("reachable", "probe_succeeded"))
    result = _run(service_health.aggregate_service_health(
        registry({"id": "a", "name": "a", "domain": "d", "probe_kind": "none"}), 100))
    assert result["schema_version"] == 1
    assert result["overall"] == "degraded"
    assert result["business_api_liveness"] == {"status": "reachable", "reason": "request_served"}
    row = result["services"][0]
    assert row["monitoring_configured"] is False
    assert row["probe_kind"] == "none"
    assert row["latency_ms"] is None


def test_serialized_report_never_leaks_internals(monkeypatch):
    class Handler(_JsonHandler):
        body = b'{"status":"ok","secret":"hunter2"}'
    server, thread, port = _serve(Handler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
    finally:
        server.shutdown()
        thread.join(timeout=2)
    dumped = json.dumps(result).lower()
    assert "http://" not in dumped
    assert "https://" not in dumped
    assert "127.0.0.1" not in dumped
    assert "hunter2" not in dumped
    assert "authorization" not in dumped
    assert "x-api-key" not in dumped
    assert "response_body" not in dumped


def test_latency_is_measured_and_plausible():
    class Handler(_JsonHandler):
        body = b'{"status":"ok"}'
    server, thread, port = _serve(Handler)
    try:
        result = _run(service_health.aggregate_service_health(
            registry({"id": "s", "name": "s", "domain": "d",
                      "origin": f"http://127.0.0.1:{port}", "path": "/health",
                      "probe_kind": "liveness"}), 100))
        latency = result["services"][0]["latency_ms"]
        assert isinstance(latency, int)
        assert 0 <= latency <= 100
    finally:
        server.shutdown()
        thread.join(timeout=2)