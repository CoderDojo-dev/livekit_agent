"""Contract test for the additive customer ledger read."""
from __future__ import annotations

from uuid import uuid4

from business_api.repositories import SupervisionRepository
from sqlalchemy.orm import Session


def test_customer_ledger_unknown_customer_returns_none(db_session: Session) -> None:
    """Mirrors customer_360: a missing customer yields None so the route can 404."""
    repo = SupervisionRepository(db_session)
    assert repo.customer_ledger(str(uuid4())) is None