"""Cookbook 4 - agent_activity() truthfulness: set-based aggregation over a
UTC half-open window, non-exclusive attributed call duration per persona, and
provider-reported token telemetry (null vs real zero preserved).

The old per-persona loop (N+1) is gone; these tests pin the five fixed
aggregation queries and the dense daily response contract.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

from business_api.repositories import SupervisionRepository

from conftest import make_staff_account
from persistence.models.conversation import AgentUsageEvent, CallSession, Turn

ADMIN = ("admin@test.local", "a-long-enough-password")
ADVISOR = ("advisor@test.local", "another-long-password")


class _FrozenClock(datetime.datetime):
    """datetime subclass with a fixed `now`, monkeypatched into repositories."""

    fixed: datetime.datetime | None = None

    @classmethod
    def now(cls, tz=None):
        assert cls.fixed is not None, "frozen clock not set"
        return cls.fixed if tz is None else cls.fixed.astimezone(tz)


def _seed_call(
    db_session,
    *,
    personas=(),
    duration=None,
    at=None,
    transcript="x",
) -> uuid.UUID:
    session_id = uuid.uuid4()
    db_session.add(
        CallSession(
            id=session_id,
            channel="voice",
            # Default anchor sits safely inside the half-open window: a
            # microsecond-equal event would land exactly on the exclusive end
            # boundary (to_ts) and be silently excluded (host clock noise).
            start_time=at or (
                datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
            ),
            duration_seconds=duration,
        )
    )
    db_session.flush()
    for index, persona in enumerate(personas, start=1):
        db_session.add(
            Turn(
                session_id=session_id,
                turn_index=index,
                speaker="agent",
                active_agent=persona,
                transcript_masked=transcript,
            )
        )
    db_session.flush()
    return session_id


def _seed_tokens(db_session, session_id, agent, *, input_tokens, output_tokens, at=None) -> None:
    db_session.add(
        AgentUsageEvent(
            session_id=session_id,
            agent=agent,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            # Same end-boundary margin as _seed_call (see note there).
            occurred_at=at or (
                datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
            ),
        )
    )
    db_session.flush()


def _persona(report: dict, name: str) -> dict:
    return next(row for row in report["personas"] if row["persona"] == name)


# ---- call attribution ------------------------------------------------------

def test_single_persona_call(db_session):
    _seed_call(db_session, personas=["Cb4SingleAgent"], duration=120)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4SingleAgent")

    assert probe["attributed_calls"] == 1
    assert probe["completed_calls"] == 1
    assert report["totals"]["global_unique_calls"] == 1
    assert report["totals"]["persona_call_attributions"] == 1


def test_handoff_call(db_session):
    _seed_call(db_session, personas=["Cb4TriageAgent", "Cb4BillingAgent"], duration=300)

    report = SupervisionRepository(db_session).agent_activity(days=1)

    assert _persona(report, "Cb4TriageAgent")["attributed_calls"] == 1
    assert _persona(report, "Cb4BillingAgent")["attributed_calls"] == 1


def test_global_call_counted_once(db_session):
    _seed_call(db_session, personas=["Cb4TriageAgent", "Cb4BillingAgent", "Cb4ManagerAgent"], duration=300)

    report = SupervisionRepository(db_session).agent_activity(days=1)

    assert report["totals"]["global_unique_calls"] == 1


def test_handoff_produces_two_persona_attributions(db_session):
    _seed_call(db_session, personas=["Cb4TriageAgent", "Cb4BillingAgent"], duration=300)

    report = SupervisionRepository(db_session).agent_activity(days=1)

    assert report["totals"]["persona_call_attributions"] == 2


def test_whole_duration_attributed_to_both_personas(db_session):
    _seed_call(db_session, personas=["Cb4TriageAgent", "Cb4BillingAgent"], duration=300)

    report = SupervisionRepository(db_session).agent_activity(days=1)

    assert _persona(report, "Cb4TriageAgent")["attributed_call_duration_seconds"] == 300
    assert _persona(report, "Cb4BillingAgent")["attributed_call_duration_seconds"] == 300
    # Non-exclusive attribution: the same 300s call counts once per persona.
    assert report["totals"]["attributed_call_duration_seconds"] == 600


def test_null_duration_call_attributed_but_not_completed(db_session):
    _seed_call(db_session, personas=["Cb4NullDurationAgent"], duration=None)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4NullDurationAgent")

    assert probe["attributed_calls"] == 1
    assert probe["completed_calls"] == 0
    assert probe["attributed_call_duration_seconds"] == 0


def test_null_duration_excluded_from_average(db_session):
    _seed_call(db_session, personas=["Cb4AvgAgent"], duration=240)
    _seed_call(db_session, personas=["Cb4AvgAgent"], duration=None)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4AvgAgent")

    assert probe["completed_calls"] == 1
    assert probe["average_completed_call_duration_seconds"] == 240.0
    assert probe["attributed_call_duration_seconds"] == 240


# ---- token telemetry -------------------------------------------------------

def test_token_only_persona_remains(db_session):
    sid = _seed_call(db_session)
    _seed_tokens(db_session, sid, "Cb4GhostAgent", input_tokens=5, output_tokens=3)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4GhostAgent")

    assert probe["attributed_calls"] == 0
    assert probe["token_event_count"] == 1
    assert probe["provider_input_tokens"] == 5
    assert probe["provider_output_tokens"] == 3


def test_persona_without_token_events_returns_null_tokens(db_session):
    _seed_call(db_session, personas=["Cb4NoTokensAgent"], duration=60)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4NoTokensAgent")

    assert probe["provider_input_tokens"] is None
    assert probe["provider_output_tokens"] is None
    assert probe["token_event_count"] == 0
    assert report["totals"]["provider_input_tokens"] is None
    assert report["totals"]["provider_output_tokens"] is None


def test_real_zero_token_event_returns_zero(db_session):
    sid = _seed_call(db_session)
    _seed_tokens(db_session, sid, "Cb4ZeroTokensAgent", input_tokens=0, output_tokens=0)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4ZeroTokensAgent")

    assert probe["provider_input_tokens"] == 0
    assert probe["provider_output_tokens"] == 0
    assert report["totals"]["provider_input_tokens"] == 0
    assert report["totals"]["provider_output_tokens"] == 0


def test_input_output_token_sums(db_session):
    sid = _seed_call(db_session)
    _seed_tokens(db_session, sid, "Cb4SumsAgent", input_tokens=10, output_tokens=5)
    _seed_tokens(db_session, sid, "Cb4SumsAgent", input_tokens=20, output_tokens=7)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = _persona(report, "Cb4SumsAgent")

    assert probe["token_event_count"] == 2
    assert probe["provider_input_tokens"] == 30
    assert probe["provider_output_tokens"] == 12
    assert report["totals"]["provider_input_tokens"] == 30
    assert report["totals"]["provider_output_tokens"] == 12


# ---- UTC window boundaries -------------------------------------------------

def test_utc_midnight_separation(db_session):
    now = datetime.datetime.now(datetime.UTC)
    yesterday = now.date() - datetime.timedelta(days=1)
    just_before_midnight = datetime.datetime.combine(
        yesterday, datetime.time(23, 59, 59, 999999), tzinfo=datetime.UTC
    )
    midnight = datetime.datetime.combine(now.date(), datetime.time.min, tzinfo=datetime.UTC)
    _seed_call(db_session, personas=["Cb4MidnightAgent"], duration=10, at=just_before_midnight)
    _seed_call(db_session, personas=["Cb4MidnightAgent"], duration=10, at=midnight)

    report = SupervisionRepository(db_session).agent_activity(days=2)
    probe = _persona(report, "Cb4MidnightAgent")

    by_day = {point["day"]: point["attributed_calls"] for point in probe["daily"]}
    assert by_day[yesterday.isoformat()] == 1
    assert by_day[now.date().isoformat()] == 1


def test_start_boundary_inclusive(db_session, monkeypatch):
    import business_api.repositories as repositories

    _FrozenClock.fixed = datetime.datetime(2026, 8, 18, 12, 0, 0, tzinfo=datetime.UTC)
    monkeypatch.setattr(repositories, "datetime", _FrozenClock)
    try:
        _seed_call(
            db_session,
            personas=["Cb4BoundaryAgent"],
            duration=10,
            at=datetime.datetime(2026, 8, 18, 0, 0, 0, tzinfo=datetime.UTC),
        )
        report = SupervisionRepository(db_session).agent_activity(days=1)
    finally:
        _FrozenClock.fixed = None

    assert _persona(report, "Cb4BoundaryAgent")["attributed_calls"] == 1


def test_end_boundary_exclusive(db_session, monkeypatch):
    import business_api.repositories as repositories

    _FrozenClock.fixed = datetime.datetime(2026, 8, 18, 12, 0, 0, tzinfo=datetime.UTC)
    monkeypatch.setattr(repositories, "datetime", _FrozenClock)
    try:
        _seed_call(
            db_session,
            personas=["Cb4BoundaryAgent"],
            duration=10,
            at=datetime.datetime(2026, 8, 18, 12, 0, 0, tzinfo=datetime.UTC),
        )
        report = SupervisionRepository(db_session).agent_activity(days=1)
    finally:
        _FrozenClock.fixed = None

    # A call at exactly to_ts falls outside the half-open [from, to) window: the
    # persona is not discovered at all.
    assert all(row["persona"] != "Cb4BoundaryAgent" for row in report["personas"])
    assert report["totals"]["global_unique_calls"] == 0


# ---- dense daily points ----------------------------------------------------

def _assert_dense_days(db_session, days: int) -> None:
    _seed_call(db_session, personas=["Cb4DenseAgent"], duration=10)

    report = SupervisionRepository(db_session).agent_activity(days=days)
    probe = _persona(report, "Cb4DenseAgent")

    from_day = datetime.date.fromisoformat(report["window"]["from"][:10])
    expected = [
        (from_day + datetime.timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]
    assert [point["day"] for point in probe["daily"]] == expected
    assert report["window"]["days"] == days


def test_dense_7_day_points(db_session):
    _assert_dense_days(db_session, 7)


def test_dense_14_day_points(db_session):
    _assert_dense_days(db_session, 14)


def test_dense_30_day_points(db_session):
    _assert_dense_days(db_session, 30)


# ---- structure, query shape, privacy --------------------------------------

def test_contract_shape_and_definitions(db_session):
    _seed_call(db_session, personas=["Cb4ShapeAgent"], duration=10)

    report = SupervisionRepository(db_session).agent_activity(days=7)

    assert set(report) == {"window", "definitions", "totals", "personas"}
    assert report["definitions"] == {
        "agent_kind": "persona_class",
        "duration_kind": "non_exclusive_attributed_call_duration",
        "token_source": "provider_reported",
        "token_history": "forward_only_no_backfill",
    }
    assert report["window"]["timezone"] == "UTC"


def test_empty_database(db_session):
    report = SupervisionRepository(db_session).agent_activity(days=1)

    assert report["personas"] == []
    assert report["totals"]["global_unique_calls"] == 0
    assert report["totals"]["persona_call_attributions"] == 0
    assert report["totals"]["attributed_call_duration_seconds"] == 0
    assert report["totals"]["provider_input_tokens"] is None
    assert report["totals"]["provider_output_tokens"] is None


def test_no_n_plus_one_persona_dependent_query_growth(db_session):
    _seed_call(db_session, personas=["Cb4QueryAgent"], duration=10)

    engine = db_session.get_bind()
    statements: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        SupervisionRepository(db_session).agent_activity(days=1)
        first = len(statements)

        for index in range(4):
            _seed_call(db_session, personas=[f"Cb4QueryAgent{index}"], duration=10)
        statements.clear()

        SupervisionRepository(db_session).agent_activity(days=1)
        second = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert first == 5, f"expected five fixed aggregation queries, got {first}"
    assert second == first, "query count must not grow with the persona count"


def test_no_session_ids_or_transcript_data_in_response(db_session):
    session_id = _seed_call(
        db_session,
        personas=["Cb4PrivacyAgent"],
        duration=10,
        transcript="SUPER_SECRET_CUSTOMER_TEXT",
    )

    report = SupervisionRepository(db_session).agent_activity(days=1)

    dumped = str(report)
    assert "SUPER_SECRET_CUSTOMER_TEXT" not in dumped
    assert str(session_id) not in dumped


# ---- HTTP authorization and validation (Cookbook 4 §24) --------------------

def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_activity_requires_auth(api_client):
    assert api_client.get("/api/v1/agents/activity").status_code == 401


def test_activity_forbids_conseiller(api_client, db_session: Session):
    make_staff_account(db_session, email=ADVISOR[0], password=ADVISOR[1], role="conseiller")
    token = _login(api_client, *ADVISOR)
    response = api_client.get("/api/v1/agents/activity", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["detail"] == "requires role >= superviseur"


def test_activity_allows_superviseur(api_client, db_session: Session):
    make_staff_account(db_session, email=ADVISOR[0], password=ADVISOR[1], role="superviseur")
    token = _login(api_client, *ADVISOR)
    response = api_client.get("/api/v1/agents/activity", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["window"]["days"] == 30


def test_activity_allows_administrateur(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    response = api_client.get("/api/v1/agents/activity", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["window"]["days"] == 30


def test_activity_rejects_invalid_days(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    for query in ("days=0", "days=366", "days=abc"):
        response = api_client.get(f"/api/v1/agents/activity?{query}", headers=_auth(token))
        assert response.status_code == 422, query