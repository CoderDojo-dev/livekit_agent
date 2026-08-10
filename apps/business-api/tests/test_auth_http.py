"""End-to-end authentication and authorisation over real HTTP.

These are the P0-1 regression tests. Case 1 and case 2 both return 200 on the unpatched build:
that was the vulnerability.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from conftest import make_staff_account

ADMIN = ("admin@test.local", "a-long-enough-password")
ADVISOR = ("advisor@test.local", "another-long-password")


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- 1-2: the vulnerability itself -------------------------------------------------

def test_no_credential_is_refused(api_client):
    assert api_client.get("/api/v1/customers").status_code == 401


def test_forged_x_role_header_is_ignored(api_client):
    response = api_client.get(
        "/api/v1/jobs/integrity", headers={"X-Role": "administrateur"}
    )
    assert response.status_code == 401


def test_health_stays_open(api_client):
    assert api_client.get("/health").status_code == 200


# ---- 3-6: the happy path and the rank matrix ---------------------------------------

def test_valid_session_reaches_its_rank(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    assert api_client.get("/api/v1/jobs/integrity", headers=_auth(token)).status_code == 200


def test_one_rank_below_is_forbidden(api_client, db_session: Session):
    make_staff_account(db_session, email=ADVISOR[0], password=ADVISOR[1], role="conseiller")
    token = _login(api_client, *ADVISOR)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    response = api_client.get("/api/v1/tickets", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["detail"] == "requires role >= superviseur"


def test_wrong_password_is_refused(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    response = api_client.post(
        "/api/v1/auth/login", json={"email": ADMIN[0], "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_unknown_email_gives_the_same_answer(api_client):
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "nobody@test.local", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


# ---- 7-9: session lifecycle ---------------------------------------------------------

def test_logout_kills_the_token_immediately(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    assert api_client.post("/api/v1/auth/logout", headers=_auth(token)).status_code == 200
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 401


def test_garbage_token_is_refused(api_client):
    assert api_client.get("/api/v1/customers", headers=_auth("not-a-token")).status_code == 401
    response = api_client.get("/api/v1/customers", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


def test_revoke_all_closes_every_session(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    first = _login(api_client, *ADMIN)
    second = _login(api_client, *ADMIN)
    assert api_client.post(
        "/api/v1/auth/sessions/revoke-all", headers=_auth(first)
    ).status_code == 200
    assert api_client.get("/api/v1/customers", headers=_auth(first)).status_code == 401
    assert api_client.get("/api/v1/customers", headers=_auth(second)).status_code == 401


# ---- 10-11: the machine principal ----------------------------------------------------

def test_internal_key_is_conseiller_and_no_higher(api_client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    machine = {"X-API-Key": "test-internal-key"}
    assert api_client.get("/api/v1/advisors/on-call", headers=machine).status_code == 200
    # The worker must not be able to reach a supervisor or admin surface.
    assert api_client.get("/api/v1/tickets", headers=machine).status_code == 403
    assert api_client.get("/api/v1/jobs/integrity", headers=machine).status_code == 403


def test_wrong_internal_key_is_refused(api_client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    response = api_client.get("/api/v1/advisors/on-call", headers={"X-API-Key": "nope"})
    assert response.status_code == 401