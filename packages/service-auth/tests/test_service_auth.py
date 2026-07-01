"""Offline tests: auth is a no-op without a key, and enforces the header when set."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from service_auth import internal_headers, require_internal_key


class _Req:
    class _U:
        path = "/context/x"
    url = _U()


def test_noop_without_key(monkeypatch) -> None:
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    require_internal_key(_Req(), x_api_key=None)  # must not raise
    assert internal_headers() == {}


def test_enforced_with_key(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    assert internal_headers() == {"X-API-Key": "s3cret"}
    with pytest.raises(HTTPException):
        require_internal_key(_Req(), x_api_key="wrong")
    require_internal_key(_Req(), x_api_key="s3cret")  # correct -> ok


def test_health_is_open(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    req = _Req()
    req.url.path = "/health"
    require_internal_key(req, x_api_key=None)  # probes allowed