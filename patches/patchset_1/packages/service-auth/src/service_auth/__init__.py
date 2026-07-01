"""Internal service-to-service authentication (report item 17).

A single shared key (`INTERNAL_API_KEY`) gates the *internal* services. It is intentionally
**opt-in**: if the env var is unset (dev / tests), the dependency is a no-op and clients send no
header - so nothing breaks locally. In staging/prod, set the key everywhere and every internal call
must present `X-API-Key`. `/health` is always allowed so container probes keep working.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

_HEALTH_PATHS = {"/health", "/healthz", "/livez", "/readyz"}


def _expected_key() -> str | None:
    return os.getenv("INTERNAL_API_KEY")


def require_internal_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 403 unless `X-API-Key` matches. No-op when the key is unset (dev)."""
    expected = _expected_key()
    if not expected:
        return  # auth disabled in dev / tests
    if request.url.path in _HEALTH_PATHS:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden: invalid internal key")


def internal_headers() -> dict[str, str]:
    """Headers a client should send to an internal service ({} when auth is disabled)."""
    key = _expected_key()
    return {"X-API-Key": key} if key else {}