"""Batch 5 — escalation customer identity projection (Cookbook 5).

The projection resolves each case's customer identity by precedence:
case.customer_id -> CallSession.customer_id -> null, with batched lookups
(never one query per case) and a hard 200-row cap applied AFTER filtering.

Dangling ids (rows written before the FK was enforced, or replication-role
imports) must keep the id and yield null name/VIP; soft-deleted customers
keep their historical name/VIP. Tests that fabricate dangling rows bypass
the FK with session_replication_role = replica (the suite's postgres user is
the container superuser); each db_session fixture owns its connection and
rolls its transaction back, so nothing leaks.
"""
from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from business_api.repositories import _ESCALATION_LIMIT, SupervisionRepository
from conftest import make_staff_account
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from persistence.models.audit import AuditLedgerEntry
from persistence.models.conversation import CallSession, EscalationCase
from persistence.models.crm import Customer

IDENTITY_KEYS = ("customer_id", "customer_name", "customer_vip")


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_customer(
    db_session: Session, *, first: str, last: str, vip: bool = False, deleted: bool = False
) -> Customer:
    customer = Customer(
        national_id=f"nat-{uuid.uuid4().hex[:16]}",
        first_name=first,
        last_name=last,
        vip_flag=vip,
    )
    if deleted:
        customer.deleted_at = datetime.now(UTC)
    db_session.add(customer)
    db_session.flush()
    return customer


def _make_case(
    db_session: Session,
    *,
    case_customer_id=None,
    session_customer_id=None,
    trigger: str = "data_breach",
    target: str = "human_advisor",
    resolution: str | None = None,
    created_at: datetime | None = None,
) -> tuple[EscalationCase, CallSession]:
    session = CallSession(customer_id=session_customer_id)
    db_session.add(session)
    db_session.flush()
    case = EscalationCase(
        session_id=session.id,
        customer_id=case_customer_id,
        trigger=trigger,
        target=target,
        dossier={"intent": "data_breach"},
        resolution=resolution,
    )
    if created_at is not None:
        case.created_at = created_at
    db_session.add(case)
    db_session.flush()
    return case, session


@pytest.fixture
def close_scope(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """The close route runs inside session_scope() (its own session + commit). Point it at the
    test transaction so the close and its audit entry land inside the rolled-back fixture —
    the same committed-visibility pattern the suite uses everywhere else.
    """

    @contextlib.contextmanager
    def _test_scope():
        yield db_session

    monkeypatch.setattr("business_api.main.session_scope", _test_scope)


# ---- projection matrix ------------------------------------------------------------

def test_projection_precedence_and_fallbacks(db_session: Session) -> None:
    direct = _make_customer(db_session, first="Direct", last="Case", vip=True)
    session_owner = _make_customer(db_session, first="Session", last="Owner", vip=False)

    case_direct, _ = _make_case(
        db_session, case_customer_id=direct.id, session_customer_id=session_owner.id
    )
    case_fallback, _ = _make_case(
        db_session, case_customer_id=None, session_customer_id=session_owner.id
    )
    case_none, _ = _make_case(db_session, case_customer_id=None, session_customer_id=None)

    # Dangling ids cannot exist through the FK; fabricate them the way an imported /
    # pre-FK dataset would, then restore normal enforcement on this connection.
    dangling_direct = dangling_fallback = dangling_session = None
    db_session.execute(text("SET session_replication_role = replica"))
    try:
        dangling_direct, _ = _make_case(
            db_session, case_customer_id=uuid.uuid4(), session_customer_id=session_owner.id
        )
        dangling_fallback, dangling_session = _make_case(
            db_session, case_customer_id=None, session_customer_id=uuid.uuid4()
        )
    finally:
        db_session.execute(text("SET session_replication_role = origin"))

    by_id = {c["id"]: c for c in SupervisionRepository(db_session).escalations("open")}

    got = by_id[str(case_direct.id)]
    assert got["customer_id"] == str(direct.id), "the case's own id wins over the session's"
    assert got["customer_name"] == "Direct Case"
    assert got["customer_vip"] is True

    got = by_id[str(case_fallback.id)]
    assert got["customer_id"] == str(session_owner.id), "the session fills a missing case id"
    assert got["customer_name"] == "Session Owner"
    assert got["customer_vip"] is False

    got = by_id[str(case_none.id)]
    assert got["customer_id"] is None
    assert got["customer_name"] is None
    assert got["customer_vip"] is None, "unresolved identity is null, never false"

    got = by_id[str(dangling_direct.id)]
    assert got["customer_id"] == str(dangling_direct.customer_id), "a dangling direct id is kept"
    assert got["customer_name"] is None
    assert got["customer_vip"] is None

    got = by_id[str(dangling_fallback.id)]
    assert got["customer_id"] == str(dangling_session.customer_id), (
        "a dangling fallback id is kept"
    )
    assert got["customer_name"] is None
    assert got["customer_vip"] is None


def test_soft_deleted_customer_keeps_historical_identity(db_session: Session) -> None:
    gone = _make_customer(db_session, first="Gone", last="Away", vip=True, deleted=True)
    case, _ = _make_case(db_session, case_customer_id=gone.id)

    got = next(
        r for r in SupervisionRepository(db_session).escalations("open") if r["id"] == str(case.id)
    )
    assert got["customer_id"] == str(gone.id)
    assert got["customer_name"] == "Gone Away"
    assert got["customer_vip"] is True


# ---- ordering, filtering and the cap ---------------------------------------------

def test_escalations_filter_before_limit_and_cap(db_session: Session) -> None:
    base = datetime.now(UTC) - timedelta(minutes=200)
    for i in range(_ESCALATION_LIMIT + 5):
        _make_case(db_session, trigger=f"billing_{i}", created_at=base + timedelta(minutes=i))
    newest_resolved, _ = _make_case(
        db_session,
        trigger="newest_resolved",
        resolution="resolved",
        created_at=base + timedelta(minutes=300),
    )

    open_rows = SupervisionRepository(db_session).escalations("open")
    assert len(open_rows) == _ESCALATION_LIMIT, "the cap applies after the open filter"
    assert all(r["resolution"] is None for r in open_rows)
    assert str(newest_resolved.id) not in {r["id"] for r in open_rows}, (
        "a resolved case is never in the open queue, even when it is the newest row"
    )

    all_rows = SupervisionRepository(db_session).escalations("all")
    assert len(all_rows) == _ESCALATION_LIMIT
    assert all_rows[0]["id"] == str(newest_resolved.id), "newest first, hard-capped"


def test_projection_query_count_stays_flat(db_session: Session) -> None:
    baseline = len(SupervisionRepository(db_session).escalations("open"))
    for _ in range(8):
        session = CallSession(customer_id=None)
        db_session.add(session)
        db_session.flush()
        db_session.add(
            EscalationCase(
                session_id=session.id, trigger="data_breach", target="human_advisor", dossier={}
            )
        )
    db_session.flush()

    seen: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower().lstrip()
        if lowered.startswith("select"):
            for table in ("escalation_cases", "call_sessions", "customers"):
                if table in lowered:
                    seen.append(table)

    event.listen(db_session.get_bind(), "before_cursor_execute", _capture)
    try:
        rows = SupervisionRepository(db_session).escalations("open")
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", _capture)

    assert len(rows) == baseline + 8, "all eight fallback rows are projected"
    assert len(seen) <= 3, f"projection issued {len(seen)} SELECTs, expected at most 3"
    assert seen.count("escalation_cases") == 1
    assert seen.count("call_sessions") == 1
    assert seen.count("customers") == 1


# ---- close behaviour ---------------------------------------------------------------

def test_close_first_resolution_wins(db_session: Session) -> None:
    case, _ = _make_case(db_session)
    repo = SupervisionRepository(db_session)

    first = repo.close_escalation(str(case.id), "transferred")
    assert first["resolution"] == "transferred"
    assert first["id"] == str(case.id)

    again = repo.close_escalation(str(case.id), "resolved")
    assert again["resolution"] == "transferred", "the first resolution is never overwritten"

    ids = {r["id"] for r in repo.escalations("open")}
    assert str(case.id) not in ids, "a closed case leaves the open queue"


def test_close_rejects_bad_resolution_and_missing_case(db_session: Session) -> None:
    case, _ = _make_case(db_session)
    repo = SupervisionRepository(db_session)

    with pytest.raises(ValueError):
        repo.close_escalation(str(case.id), "not-a-resolution")

    assert repo.close_escalation(str(uuid.uuid4()), "resolved") == {}


def test_close_route_identity_and_audit_payload(api_client, db_session: Session, close_scope) -> None:
    customer = _make_customer(db_session, first="Routed", last="Customer", vip=True)
    case, _ = _make_case(db_session, case_customer_id=customer.id)
    make_staff_account(
        db_session,
        email="close.superviseur@test.local",
        password="a-long-enough-password",
        role="superviseur",
    )
    token = _login(api_client, "close.superviseur@test.local", "a-long-enough-password")

    listed = next(
        r
        for r in api_client.get("/api/v1/escalations", headers=_auth(token)).json()["escalations"]
        if r["id"] == str(case.id)
    )

    response = api_client.post(
        f"/api/v1/escalations/{case.id}/close", headers=_auth(token), json={"resolution": "queued"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    for key in ("id", "session_id", "trigger", "target", "dossier", "created_at", *IDENTITY_KEYS):
        assert body[key] == listed[key], key
    assert body["customer_name"] == "Routed Customer"
    assert body["customer_vip"] is True

    again = api_client.post(
        f"/api/v1/escalations/{case.id}/close", headers=_auth(token), json={"resolution": "resolved"}
    )
    assert again.status_code == 200, again.text
    assert again.json()["resolution"] == "queued", "idempotent retry keeps the first resolution"
    assert again.json()["customer_name"] == "Routed Customer"

    entries = db_session.scalars(
        select(AuditLedgerEntry)
        .where(AuditLedgerEntry.event_type == "escalation_closed")
        .where(AuditLedgerEntry.entity_reference == f"escalation_cases:{case.id}")
        .order_by(AuditLedgerEntry.seq)
    ).all()
    assert len(entries) == 2, "every close request is audited"
    for entry in entries:
        for key in IDENTITY_KEYS:
            assert key not in entry.payload, f"audit payload must not carry {key}"
    assert entries[0].payload["requested_resolution"] == "queued"
    assert entries[0].payload["resolution"] == "queued"
    assert entries[1].payload["requested_resolution"] == "resolved"
    assert entries[1].payload["resolution"] == "queued"


# ---- RBAC ---------------------------------------------------------------------------

def test_escalation_rbac(api_client, db_session: Session) -> None:
    assert api_client.get("/api/v1/escalations").status_code == 401

    make_staff_account(
        db_session,
        email="esc.conseiller@test.local",
        password="a-long-enough-password",
        role="conseiller",
    )
    conseiller = _login(api_client, "esc.conseiller@test.local", "a-long-enough-password")
    assert api_client.get("/api/v1/escalations", headers=_auth(conseiller)).status_code == 403
    assert (
        api_client.post(
            "/api/v1/escalations/00000000-0000-0000-0000-000000000000/close",
            headers=_auth(conseiller),
            json={"resolution": "resolved"},
        ).status_code
        == 403
    )

    make_staff_account(
        db_session,
        email="esc.superviseur@test.local",
        password="a-long-enough-password",
        role="superviseur",
    )
    superviseur = _login(api_client, "esc.superviseur@test.local", "a-long-enough-password")
    assert api_client.get("/api/v1/escalations", headers=_auth(superviseur)).status_code == 200

    make_staff_account(
        db_session,
        email="esc.administrateur@test.local",
        password="a-long-enough-password",
        role="administrateur",
    )
    admin = _login(api_client, "esc.administrateur@test.local", "a-long-enough-password")
    assert api_client.get("/api/v1/escalations", headers=_auth(admin)).status_code == 200