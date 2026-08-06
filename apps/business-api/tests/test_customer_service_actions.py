"""Contract test for the additive service-actions read."""
from __future__ import annotations

from uuid import uuid4

from business_api.repositories import SupervisionRepository
from sqlalchemy.orm import Session


def test_customer_service_actions_unknown_customer_returns_none(db_session: Session) -> None:
    """Mirrors customer_360 / customer_ledger: a missing customer yields None so the route 404s."""
    repo = SupervisionRepository(db_session)
    assert repo.customer_service_actions(str(uuid4())) is None
