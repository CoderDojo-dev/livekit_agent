"""The live adapters are internal callers: X-API-Key goes out iff INTERNAL_API_KEY is set.

Offline: httpx.AsyncClient is replaced with a recording stub, so no socket is opened and the
sims are not needed. The contract pinned here is the one the sims enforce app-wide via
service_auth.require_internal_key.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

import integration_adapters._http as http_layer


class _FakeResponse:
    def raise_for_status(self) -> None: ...
    def json(self) -> dict: return {"ok": True}


class _RecordingClient:
    sent: ClassVar[list[dict]] = []

    def __init__(self, **kwargs) -> None:
        self.sent.append(kwargs.get("headers") or {})

    async def __aenter__(self): return self
    async def __aexit__(self, *args) -> bool: return False
    async def post(self, path, json): return _FakeResponse()
    async def get(self, path, params=None): return _FakeResponse()


def test_key_set_sends_header(monkeypatch) -> None:
    _RecordingClient.sent = []
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    monkeypatch.setattr(http_layer.httpx, "AsyncClient", _RecordingClient)
    asyncio.run(http_layer.post_json("http://sim", "/x", {}))
    asyncio.run(http_layer.get_json("http://sim", "/x"))
    assert _RecordingClient.sent == [{"X-API-Key": "s3cret"}, {"X-API-Key": "s3cret"}]


def test_key_unset_sends_no_header(monkeypatch) -> None:
    _RecordingClient.sent = []
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setattr(http_layer.httpx, "AsyncClient", _RecordingClient)
    asyncio.run(http_layer.post_json("http://sim", "/x", {}))
    assert _RecordingClient.sent == [{}]