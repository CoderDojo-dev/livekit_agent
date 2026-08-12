"""P1-2 - run_retention() must purge auth.portal_sessions that can no longer authenticate.

Only rows whose expires_at has passed, or which were revoked at logout, may go; a forensic
grace window (_SESSION_GRACE_DAYS = 7) keeps a logout or an expiry visible to an investigation
for a week. Dry runs must purge nothing. The final test is a positive control: the pre-existing
conversation-retention block must still report its own counts from the same call.
"""
from __future__ import annotations

import datetime
import uuid

from business_api.jobs.retention import run_retention

from persistence.models.conversation import CallSession, Turn
from persistence.models.portal_identity import PortalAccount, PortalSession


def _account(db_session, email: str) -> PortalAccount:
    account = PortalAccount(
        kind="staff",
        email=email,
        password_hash="x",
        password_algo="scrypt",
        password_params="n=16384,r=8,p=1",
        role="conseiller",
        customer_id=None,
    )
    db_session.add(account)
    db_session.flush()
    return account


def _session(db_session, account: PortalAccount, *, expires_at, revoked_at=None) -> PortalSession:
    row = PortalSession(
        account_id=account.id,
        token_digest=uuid.uuid4().hex,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_dry_run_purges_nothing(db_session):
    account = _account(db_session, f"dry-{uuid.uuid4().hex[:8]}@telecom.tn")
    old = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30)
    row = _session(db_session, account, expires_at=old)

    report = run_retention(db_session, dry_run=True)

    db_session.expire_all()
    assert report.portal_sessions_purged == 0
    assert db_session.get(PortalSession, row.id) is not None


def test_long_expired_session_is_purged(db_session):
    account = _account(db_session, f"exp-{uuid.uuid4().hex[:8]}@telecom.tn")
    old = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30)
    row = _session(db_session, account, expires_at=old)

    report = run_retention(db_session, dry_run=False)

    db_session.expire_all()
    assert report.portal_sessions_purged == 1
    assert db_session.get(PortalSession, row.id) is None


def test_live_session_survives(db_session):
    account = _account(db_session, f"live-{uuid.uuid4().hex[:8]}@telecom.tn")
    future = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
    row = _session(db_session, account, expires_at=future)

    report = run_retention(db_session, dry_run=False)

    db_session.expire_all()
    assert report.portal_sessions_purged == 0
    assert db_session.get(PortalSession, row.id) is not None


def test_inside_grace_window_survives(db_session):
    """The 7-day forensic window is honoured, not ignored."""
    account = _account(db_session, f"grace-{uuid.uuid4().hex[:8]}@telecom.tn")
    recent = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
    row = _session(db_session, account, expires_at=recent)

    report = run_retention(db_session, dry_run=False)

    db_session.expire_all()
    assert report.portal_sessions_purged == 0
    assert db_session.get(PortalSession, row.id) is not None


def test_long_revoked_session_is_purged_even_with_future_expiry(db_session):
    """The or_() arm: revoked_at past the cutoff wins over a live expires_at."""
    account = _account(db_session, f"rev-{uuid.uuid4().hex[:8]}@telecom.tn")
    future = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
    revoked = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30)
    row = _session(db_session, account, expires_at=future, revoked_at=revoked)

    report = run_retention(db_session, dry_run=False)

    db_session.expire_all()
    assert report.portal_sessions_purged == 1
    assert db_session.get(PortalSession, row.id) is None


def test_conversation_retention_still_reports_its_own_counts(db_session):
    """Positive control: the pre-existing block must not be masked by a passing purge test."""
    account = _account(db_session, f"ctl-{uuid.uuid4().hex[:8]}@telecom.tn")
    _session(db_session, account, expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))

    session_id = uuid.uuid4()
    old = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=120)
    db_session.add(
        CallSession(
            id=session_id,
            channel="voice",
            start_time=old,
            audio_record_url=None,
        )
    )
    db_session.flush()
    db_session.add(
        Turn(
            session_id=session_id,
            turn_index=1,
            speaker="caller",
            active_agent="P12Control",
            transcript_masked="bonjour",
        )
    )
    db_session.flush()

    report = run_retention(db_session, dry_run=False)

    assert report.sessions_matched >= 1
    assert report.turns_anonymized >= 1
