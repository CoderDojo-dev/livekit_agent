"""Tiny async HTTP helper for the live adapters (one place for timeout/errors)."""
from __future__ import annotations

import httpx

_TIMEOUT = 8.0


async def post_json(base_url: str, path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_json(base_url: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()