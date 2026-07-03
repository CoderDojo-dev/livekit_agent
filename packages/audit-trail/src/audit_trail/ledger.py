"""Append-only, hash-chained audit ledger (cookbook section 18; Blueprint section 12.3 / ADR 5.6).

entry_hash = sha256(previous_hash | canonical_payload | timestamp). Any retroactive edit breaks
the chain and is caught by verify. Two implementations behind the same shape: an in-memory
`AuditLedger` (used in tests) and a Postgres-backed `PgAuditLedger` (used by the services).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
_AUDIT_LOCK_KEY = 8472  # pg advisory lock: serialize chain appends within a transaction


@dataclass(frozen=True)
class AuditEntry:
    """One immutable, hash-chained audit record (English payload)."""

    entry_id: str
    session_id: str
    event_type: str
    payload: dict
    previous_hash: str
    timestamp: str
    entry_hash: str


def compute_entry_hash(previous_hash: str, payload: dict, timestamp: str) -> str:
    """sha256(previous_hash | canonical(payload) | timestamp). Canonical = sorted, compact JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest_input = f"{previous_hash}|{canonical}|{timestamp}".encode()
    return hashlib.sha256(digest_input).hexdigest()


def build_entry(
    entry_id: str, session_id: str, event_type: str, payload: dict, previous_hash: str
) -> AuditEntry:
    """Build a chained entry linking to ``previous_hash``."""
    timestamp = datetime.now(UTC).isoformat()
    entry_hash = compute_entry_hash(previous_hash, payload, timestamp)
    return AuditEntry(entry_id, session_id, event_type, payload, previous_hash, timestamp, entry_hash)


def verify_chain(entries: list[AuditEntry]) -> bool:
    """Integrity job: any retroactive edit breaks the chain here."""
    expected_previous = GENESIS_HASH
    for entry in entries:
        if entry.previous_hash != expected_previous:
            return False
        if compute_entry_hash(entry.previous_hash, entry.payload, entry.timestamp) != entry.entry_hash:
            return False
        expected_previous = entry.entry_hash
    return True


class AuditLedger:
    """In-process append-only ledger (tests / fallback)."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash = GENESIS_HASH

    def append(self, session_id: str, event_type: str, payload: dict) -> AuditEntry:
        entry = build_entry(str(uuid.uuid4()), session_id, event_type, payload, self._last_hash)
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def verify(self) -> bool:
        return verify_chain(self._entries)

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


class PgAuditLedger:
    """Postgres-backed append-only ledger over audit.audit_ledger (spec section 12.3).

    append() serializes the chain with a transaction-scoped advisory lock, reads the prior
    entry_hash, computes the new hash, and inserts (flush only - the caller owns the commit, so
    the verdict/action write and its audit entry land in one transaction). Append-only by role.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, session_id, event_type: str, payload: dict, entity_reference: str | None = None):
        from persistence.models.audit import AuditLedgerEntry

        self._session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY})
        last = self._session.scalar(
            select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.desc()).limit(1)
        )
        previous_hash = last.entry_hash if last else GENESIS_HASH
        created_at = datetime.now(UTC)
        entry_hash = compute_entry_hash(previous_hash, payload, created_at.isoformat())
        row = AuditLedgerEntry(
            session_id=session_id,
            event_type=event_type,
            entity_reference=entity_reference,
            payload=payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        logger.info("audit event_type=%s hash=%s", event_type, entry_hash[:12])
        return row

    def verify(self) -> bool:
        """Recompute the whole chain; False on any break (tamper-evident)."""
        from persistence.models.audit import AuditLedgerEntry

        rows = list(self._session.scalars(select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.asc())))
        expected_previous = GENESIS_HASH
        for row in rows:
            if row.previous_hash != expected_previous:
                return False
            if compute_entry_hash(row.previous_hash, row.payload, row.created_at.isoformat()) != row.entry_hash:
                return False
            expected_previous = row.entry_hash
        return True

    def count(self) -> int:
        from persistence.models.audit import AuditLedgerEntry

        return self._session.scalar(select(func.count()).select_from(AuditLedgerEntry)) or 0