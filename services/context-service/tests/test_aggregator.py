"""Integration tests for CrmRepository (requires DATABASE_URL env var with Postgres + seeded data).

Run::

    DATABASE_URL=postgresql+psycopg://telecom:telecom@localhost:5432/telecom \\
      pytest services/context-service/tests/test_aggregator.py -v

Tests are skipped if DATABASE_URL is not set.
"""
from __future__ import annotations

import os

import pytest
from context_service.repositories import CrmRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="requires DATABASE_URL pointing to a seeded Postgres",
)


@pytest.fixture(scope="module")
def session() -> Session:
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def test_resolve_identity_known_msisdn(session: Session) -> None:
    repo = CrmRepository(session)
    result = repo.resolve_identity("+21620155320")
    assert result is not None
    customer, subscription = result
    assert customer.first_name and subscription.msisdn


def test_resolve_identity_unknown_msisdn(session: Session) -> None:
    repo = CrmRepository(session)
    assert repo.resolve_identity("+21600000000") is None


def test_build_customer360_for_known_caller(session: Session) -> None:
    snap = CrmRepository(session).build_customer360("+21620155320")
    assert snap is not None
    assert snap.msisdn == "+21620155320"
    assert snap.full_name


def test_build_customer360_unknown_caller(session: Session) -> None:
    assert CrmRepository(session).build_customer360("+21600000000") is None


def test_verify_identity_correct_answer(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    assert repo.verify_identity(str(customer.id), customer.national_id[-4:]) is True


def test_verify_identity_wrong_answer(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    assert repo.verify_identity(str(customer.id), "0000") is False


def test_verify_identity_unknown_customer(session: Session) -> None:
    assert CrmRepository(session).verify_identity("00000000-0000-0000-0000-000000000000", "4087") is False


def test_get_invoices(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    invoices = repo.get_invoices(str(customer.id))
    assert isinstance(invoices, list)


def test_get_balance(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21629744108")
    assert resolved is not None
    customer, _ = resolved
    balance = repo.get_balance(str(customer.id))
    if balance is not None:
        assert balance.credit >= 0
