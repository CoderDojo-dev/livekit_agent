"""Tiny async HTTP helper for the live adapters (one place for timeout/errors).

The adapters are INTERNAL callers: the sims (and any in-platform stand-in) gate on
``X-API-Key`` via service_auth.require_internal_key. ``internal_headers()`` returns {} when
INTERNAL_API_KEY is unset, so dev/tests are untouched; it is read per-request, so key rotation
needs no restart of the caller.
"""
from __future__ import annotations

import httpx

from service_auth import internal_headers

_TIMEOUT = 8.0


async def post_json(base_url: str, path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(
        base_url=base_url, timeout=_TIMEOUT, headers=internal_headers()
    ) as client:
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_json(base_url: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(
        base_url=base_url, timeout=_TIMEOUT, headers=internal_headers()
    ) as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()