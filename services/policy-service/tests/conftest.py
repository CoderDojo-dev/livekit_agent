"""Live-database fixtures for the policy service.

The verdict path fails inside the Postgres driver, not inside SQLAlchemy, so an in-memory double
would prove nothing here: it is psycopg that refuses to serialize a datetime into JSONB. Each test
runs in a transaction that is rolled back, so the audited, append-only verdict ledger is never
polluted by a test row.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_session():
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://telecom:telecom@localhost:5432/telecom")
    engine = create_engine(url, future=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
