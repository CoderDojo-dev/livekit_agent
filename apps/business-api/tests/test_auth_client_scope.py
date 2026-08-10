"""A client account can only ever read its own customer record."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from business_api.infrastructure.auth import cin, passwords
from persistence.models.auth import CustomerCredential
from persistence.models.crm import Customer, Subscription
from persistence.models.portal_identity import PortalAccount


def _customer(session: Session, suffix: str) -> Customer:
    customer = Customer(
        national_id=f"CIN{suffix}",
        first_name="Test",
        last_name=f"Case{suffix}",
        preferred_language="fr",
        status="active",
    )
    session.add(customer)
    session.flush()
    session.add(
        Subscription(
            customer_id=customer.id,
            msisdn=f"+2169{suffix}",
            plan_type="PREPAID",
            status="ACTIVE",
        )
    )
    session.add(
        CustomerCredential(
            customer_id=customer.id,
            verifier_type="cin_last4",
            verifier_digest=cin.digest(str(customer.id), suffix[-4:]),
            key_version=1,
            active=True,
        )
    )
    session.flush()
    return customer


def _client_account(session: Session, customer: Customer, email: str) -> PortalAccount:
    algorithm, params, encoded = passwords.hash_password("a-long-enough-password")
    account = PortalAccount(
        kind="client",
        email=email,
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role="client",
        customer_id=customer.id,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()
    return account


def test_me_profile_returns_only_the_token_owner(api_client, db_session: Session):
    alice = _customer(db_session, "110011")
    _customer(db_session, "220022")
    _client_account(db_session, alice, "alice@test.local")

    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@test.local", "password": "a-long-enough-password"},
    ).json()["token"]

    body = api_client.get(
        "/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"}
    ).json()
    # §12.6-adjusted: customer_360 returns the customer id at the TOP LEVEL (verified live),
    # not nested under "customer". Adjusting the assertion, never the endpoint.
    assert body["customer_id"] == str(alice.id)


def test_client_cannot_reach_staff_endpoints(api_client, db_session: Session):
    alice = _customer(db_session, "330033")
    _client_account(db_session, alice, "alice2@test.local")
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice2@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    # role "client" is absent from _ROLE_RANK, so role_rank() is 0 and every staff gate refuses.
    assert api_client.get("/api/v1/customers", headers=auth).status_code == 403
    assert api_client.get("/api/v1/tickets", headers=auth).status_code == 403
    assert api_client.get("/api/v1/jobs/integrity", headers=auth).status_code == 403


def test_staff_cannot_use_the_client_surface(api_client, db_session: Session):
    from conftest import make_staff_account

    make_staff_account(
        db_session, email="boss@test.local", password="a-long-enough-password", role="administrateur"
    )
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "boss@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    response = api_client.get(
        "/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_signup_claims_an_existing_subscriber(api_client, db_session: Session):
    customer = _customer(db_session, "440044")

    response = api_client.post(
        "/api/v1/auth/signup",
        json={
            "msisdn": "+2169440044",
            "cin_last4": "0044",
            "email": "claim@test.local",
            "password": "a-long-enough-password",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["customer_id"] == str(customer.id)

    # Wrong CIN, unknown number, and a second claim all give the identical generic answer.
    for payload in (
        {"msisdn": "+2169440044", "cin_last4": "9999"},
        {"msisdn": "+21600000000", "cin_last4": "0044"},
    ):
        again = api_client.post(
            "/api/v1/auth/signup",
            json={**payload, "email": "other@test.local", "password": "a-long-enough-password"},
        )
        assert again.status_code == 401
        assert again.json()["detail"] == "We could not match those details to an account."


def test_uuid_is_never_taken_from_the_request(api_client, db_session: Session):
    """There is no path parameter to tamper with: /me/profile takes no identifier at all."""
    alice = _customer(db_session, "550055")
    _client_account(db_session, alice, "alice3@test.local")
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice3@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    # A crafted query string cannot redirect the read.
    body = api_client.get(
        f"/api/v1/me/profile?customer_id={uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    # §12.6-adjusted: flat payload key, same as test_me_profile_returns_only_the_token_owner.
    assert body["customer_id"] == str(alice.id)