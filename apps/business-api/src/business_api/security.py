"""API-layer RBAC (spec section 19): conseiller < superviseur < administrateur.

The role matrix is enforced here. Identity is established by
business_api.infrastructure.auth.principal.current_principal(): either a bearer session token
issued by POST /api/v1/auth/login and revalidated against auth.portal_sessions, or the internal
service key (INTERNAL_API_KEY) presented by the voice worker.

The `X-Role` header is NO LONGER READ. Before P0-1 an absent header fell back to an
environment-sourced default role (administrateur), which made every endpoint reachable
by an unauthenticated caller. A request without a valid credential now fails closed with 401.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException

from business_api.infrastructure.auth.principal import Principal, current_principal

_ROLE_RANK = {"conseiller": 1, "superviseur": 2, "administrateur": 3}


def role_rank(role: str | None) -> int:
    """Numeric rank for a role name (0 if unknown)."""
    return _ROLE_RANK.get(role or "", 0)


def require_role(minimum: str):
    """Dependency factory: 403 unless the caller's role is at least ``minimum``.

    401 (not 403) when there is no authenticated caller at all - the two answers mean different
    things and the front end already separates them (isUnauthenticated / isForbidden).
    """
    minimum_rank = _ROLE_RANK[minimum]

    def _dependency(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> str:
        if role_rank(principal.role) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
        return principal.role

    return _dependency