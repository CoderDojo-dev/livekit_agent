"""DB-backed tests: business-api suites ran unit-only before, but reserve()/claim_next()
execute real SQL (pg_advisory_xact_lock is Postgres-only). This fixture borrows the live
engine (docker postgres) inside a rolled-back transaction so tests never leave a trace."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from persistence.engine import get_engine
from persistence.models.routing import Advisor, AdvisorShift

MONDAY = 0


@pytest.fixture
def db_session() -> Session:
    engine = get_engine()
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, future=True)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def make_advisor(session: Session, *, name: str, language: str = "fr") -> Advisor:
    """An on-call advisor with a Monday 08:00-18:00 (local) shift, ready to be booked."""
    advisor = Advisor(
        full_name=name,
        language=language,
        skills="general",
        status="available",
        max_concurrent_calls=1,
        active_calls=0,
        is_on_call=True,
        is_active=True,
    )
    session.add(advisor)
    session.flush()
    shift = AdvisorShift(
        advisor_id=advisor.id,
        weekday=MONDAY,
        start_minute=480,   # 08:00 local
        end_minute=1080,    # 18:00 local
        is_active=True,
    )
    session.add(shift)
    session.flush()
    return advisor


def monday_slot(hour: int = 13, minute: int = 0) -> datetime:
    """The next Monday at hour/minute UTC - always inside the fixture shift (08:00-18:00 local)."""
    now = datetime.now(UTC)
    days_ahead = (MONDAY - now.weekday()) % 7 or 7
    day = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute,
                                                     second=0, microsecond=0, tzinfo=UTC)
    return day


@pytest.fixture
def api_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """HTTP client bound to the rolled-back test transaction.

    get_session is overridden so every request inside a test shares the fixture's session and
    leaves no trace, exactly like db_session. Imported lazily so collecting this module never
    requires a database.
    """
    from business_api.infrastructure.auth import rate_limit
    from business_api.main import app

    from persistence import get_session

    # A shared 32+ char key so cin.digest() is computable in tests without touching the real one.
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", "t" * 48)
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    rate_limit.clear_all()

    app.dependency_overrides[get_session] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)
        rate_limit.clear_all()


def make_staff_account(session: Session, *, email: str, password: str, role: str):
    """A staff login usable by the HTTP tests."""
    from datetime import UTC, datetime

    from business_api.infrastructure.auth import passwords

    from persistence.models.portal_identity import PortalAccount

    algorithm, params, encoded = passwords.hash_password(password)
    account = PortalAccount(
        kind="staff",
        email=email.lower(),
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role=role,
        customer_id=None,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()
    return account
