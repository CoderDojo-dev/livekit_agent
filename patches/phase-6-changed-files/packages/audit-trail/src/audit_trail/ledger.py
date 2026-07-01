"""Append-only, hash-chained audit ledger (cookbook section 18; Blueprint section 12.3 / ADR 5.6).

entry_hash = sha256(previous_hash | canonical_payload | timestamp). Any retroactive edit breaks
the chain and is caught by verify_chain. Phase 11 swaps the in-process store for an append-only
PostgreSQL table behind this same API.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    """One immutable, hash-chained audit record (English payload)."""

    entry_id: str
    session_id: str
    event_type: str  # "policy_verdict" | "outbound_guardrail" | "execution_result" | "consent"
    payload: dict
    previous_hash: str
    timestamp: str
    entry_hash: str


def _compute_hash(previous_hash: str, payload: dict, timestamp: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest_input = f"{previous_hash}|{canonical}|{timestamp}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def build_entry(
    entry_id: str, session_id: str, event_type: str, payload: dict, previous_hash: str
) -> AuditEntry:
    """Build a chained entry linking to ``previous_hash``."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry_hash = _compute_hash(previous_hash, payload, timestamp)
    return AuditEntry(
        entry_id=entry_id,
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        previous_hash=previous_hash,
        timestamp=timestamp,
        entry_hash=entry_hash,
    )


def verify_chain(entries: list[AuditEntry]) -> bool:
    """Integrity job (Blueprint section 12.3): any retroactive edit breaks the chain here."""
    expected_previous = GENESIS_HASH
    for entry in entries:
        if entry.previous_hash != expected_previous:
            return False
        if _compute_hash(entry.previous_hash, entry.payload, entry.timestamp) != entry.entry_hash:
            return False
        expected_previous = entry.entry_hash
    return True


class AuditLedger:
    """In-process append-only ledger. One per service; persists to Postgres in Phase 11."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash = GENESIS_HASH

    def append(self, session_id: str, event_type: str, payload: dict) -> AuditEntry:
        """Append a chained entry and structured-log it; never raises on a valid payload."""
        entry = build_entry(str(uuid.uuid4()), session_id, event_type, payload, self._last_hash)
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        logger.info(
            "audit event_type=%s verdict=%s rule_id=%s hash=%s",
            event_type,
            payload.get("verdict"),
            payload.get("rule_id"),
            entry.entry_hash[:12],
        )
        return entry

    def verify(self) -> bool:
        """Return True iff the whole chain is intact."""
        return verify_chain(self._entries)

    @property
    def entries(self) -> list[AuditEntry]:
        """A copy of the current entries."""
        return list(self._entries)