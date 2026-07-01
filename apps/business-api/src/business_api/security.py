"""API-layer RBAC (spec section 19): conseiller < superviseur < administrateur.

The role matrix is enforced here. Real identity is OIDC at integration time; in this build the
role is taken from the `X-Role` header (or BUSINESS_API_DEFAULT_ROLE for local use).
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException

_ROLE_RANK = {"conseiller": 1, "superviseur": 2, "administrateur": 3}


def role_rank(role: str | None) -> int:
    """Numeric rank for a role name (0 if unknown)."""
    return _ROLE_RANK.get(role or "", 0)


def require_role(minimum: str):
    """Dependency factory: 403 unless the caller's role is at least ``minimum``."""
    minimum_rank = _ROLE_RANK[minimum]

    def _dependency(x_role: str | None = Header(default=None)) -> str:
        role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
        if role_rank(role) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
        return role

    return _dependency