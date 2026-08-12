"""Retention & purge job (CDC section 8.3 / Blueprint section 12.4): an AUDITED workflow, never an ad-hoc DELETE.

At the retention boundary: audio pointers are cleared (the blob is purged from MinIO by the same
scheduler at integration) and transcripts are anonymized. Every run writes an audit entry, so the
purge itself is part of the tamper-evident record. Supports dry_run for safe inspection.
"""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from object_storage import get_store
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.conversation import CallSession, Turn
from persistence.models.portal_identity import PortalSession

_PURGED = "[purged]"

# P1-2 - auth.portal_sessions is the one table P0-1 added that grows without bound. A row whose
# expires_at has passed, or which was revoked at logout, can no longer authenticate anything
# (portal_auth checks both on every request), so removing it changes no behaviour. The grace
# window keeps a logout or an expiry visible to an investigation for a week first. This is a
# separate horizon from the conversation retention window on purpose: unrelated lifecycles.
_SESSION_GRACE_DAYS = 7


@dataclass
class RetentionReport:
    """Outcome of a retention run."""

    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool
    portal_sessions_purged: int = 0


def cutoff_date(retention_days: int, now: datetime | None = None) -> datetime:
    """The boundary before which data is purged/anonymized."""
    now = now or datetime.now(UTC)
    return now - timedelta(days=retention_days)


def run_retention(session: Session, retention_days: int = 90, dry_run: bool = True) -> RetentionReport:
    """Anonymize transcripts + clear audio pointers for sessions older than the window (audited)."""
    cutoff = cutoff_date(retention_days)
    old_ids = list(session.scalars(select(CallSession.id).where(CallSession.start_time < cutoff)))
    matched = len(old_ids)
    turns_anonymized = 0

    if not dry_run and matched:
        result = session.execute(
            update(Turn)
            .where(Turn.session_id.in_(old_ids), Turn.transcript_masked.is_not(None),
                   Turn.transcript_masked != _PURGED)
            .values(transcript_masked=_PURGED)
        )
        turns_anonymized = result.rowcount or 0
        store = get_store()
        if store.enabled:
            for url in session.scalars(
                select(CallSession.audio_record_url).where(
                    CallSession.id.in_(old_ids), CallSession.audio_record_url.is_not(None)
                )
            ):
                with suppress(Exception):
                    store.delete(url)  # type: ignore[arg-type]
        session.execute(update(CallSession).where(CallSession.id.in_(old_ids)).values(audio_record_url=None))
        PgAuditLedger(session).append(
            None, "data_retention",
            {"cutoff": cutoff.isoformat(), "sessions": matched, "turns_anonymized": turns_anonymized},
            entity_reference="retention_job",
        )
        session.commit()

    portal_sessions_purged = 0
    if not dry_run:
        session_cutoff = datetime.now(UTC) - timedelta(days=_SESSION_GRACE_DAYS)
        purged = session.execute(
            delete(PortalSession).where(
                or_(
                    PortalSession.expires_at < session_cutoff,
                    PortalSession.revoked_at < session_cutoff,
                )
            )
        )
        portal_sessions_purged = purged.rowcount or 0
        if portal_sessions_purged:
            PgAuditLedger(session).append(
                None, "data_retention",
                {
                    "cutoff": session_cutoff.isoformat(),
                    "portal_sessions_purged": portal_sessions_purged,
                },
                entity_reference="retention_job",
            )
        session.commit()

    return RetentionReport(
        cutoff=cutoff.isoformat(), sessions_matched=matched,
        turns_anonymized=turns_anonymized, dry_run=dry_run,
        portal_sessions_purged=portal_sessions_purged,
    )
