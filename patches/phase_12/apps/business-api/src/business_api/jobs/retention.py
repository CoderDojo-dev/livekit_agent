"""Retention & purge job (CDC section 8.3 / Blueprint section 12.4): an AUDITED workflow, never an ad-hoc DELETE.

At the retention boundary: audio pointers are cleared (the blob is purged from MinIO by the same
scheduler at integration) and transcripts are anonymized. Every run writes an audit entry, so the
purge itself is part of the tamper-evident record. Supports dry_run for safe inspection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.conversation import CallSession, Turn

_PURGED = "[purged]"


@dataclass
class RetentionReport:
    """Outcome of a retention run."""

    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool


def cutoff_date(retention_days: int, now: datetime | None = None) -> datetime:
    """The boundary before which data is purged/anonymized."""
    now = now or datetime.now(timezone.utc)
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
        session.execute(update(CallSession).where(CallSession.id.in_(old_ids)).values(audio_record_url=None))
        PgAuditLedger(session).append(
            None, "data_retention",
            {"cutoff": cutoff.isoformat(), "sessions": matched, "turns_anonymized": turns_anonymized},
            entity_reference="retention_job",
        )
        session.commit()

    return RetentionReport(
        cutoff=cutoff.isoformat(), sessions_matched=matched,
        turns_anonymized=turns_anonymized, dry_run=dry_run,
    )