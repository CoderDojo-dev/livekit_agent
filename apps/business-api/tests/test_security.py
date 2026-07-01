"""Offline tests for the RBAC role hierarchy (no DB)."""
from __future__ import annotations

from business_api.security import role_rank


def test_role_hierarchy() -> None:
    assert role_rank("conseiller") < role_rank("superviseur") < role_rank("administrateur")
    assert role_rank("unknown") == 0
    assert role_rank(None) == 0