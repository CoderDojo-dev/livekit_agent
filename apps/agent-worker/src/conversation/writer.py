"""Non-blocking writer for the conversation record (spec section 11; ADR adaptation 3).

The worker is real-time, so NOTHING here runs on the voice path: callers enqueue plain dicts
(constant time), a single background task drains the queue and performs the actual Postgres
writes in a thread (sync SQLAlchemy off the event loop). If the DB is down, writes are logged
and dropped - the call is never affected. Transcripts are PII-masked before they leave the worker.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)


def sentiment_label(score: float) -> str:
    """Map a sentiment score to the conversation.sentiment_samples label vocabulary."""
    if score <= -0.7:
        return "angry"
    if score <= -0.35:
        return "negative"
    if score >= 0.35:
        return "positive"
    return "neutral"


class ConversationWriter:
    """Enqueue-and-forget writer; one instance per call."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._masker = PiiMasker()
        self._session_db_id: str | None = None
        self._start_time: datetime | None = None
        self._turn_index = 0

    def start(self) -> None:
        """Launch the background drain task."""
        if self._task is None:
            self._task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is None:
                    break
                await asyncio.to_thread(self._write, item)
            except Exception as exc:
                logger.warning("conversation write dropped (%s): %s", (item or {}).get("kind"), exc)
            finally:
                self._queue.task_done()

    def _write(self, item: dict) -> None:
        from persistence.engine import session_scope
        from persistence.models.conversation import (
            CallbackSchedule,
            CallSession,
            EscalationCase,
            SentimentSample,
            Turn,
        )

        kind = item["kind"]
        row = item.get("row", {})
        with session_scope() as session:
            if kind == "session_start":
                session.add(CallSession(**row))
            elif kind == "turn":
                session.add(Turn(**row))
            elif kind == "sentiment":
                session.add(SentimentSample(**row))
            elif kind == "escalation":
                session.add(EscalationCase(**row))
            elif kind == "callback":
                session.add(CallbackSchedule(**row))
            elif kind == "consent":
                from audit_trail import PgAuditLedger
                from persistence.models.crm import ConsentRecord

                record = ConsentRecord(**row)
                session.add(record)
                session.flush()
                PgAuditLedger(session).append(
                    row["session_id"], "consent",
                    {"granted": row["granted"], "consent_type": row["consent_type"]},
                    entity_reference=f"consent_records:{record.id}",
                )
            elif kind == "session_finish":
                obj = session.get(CallSession, item["session_db_id"])
                if obj is not None:
                    obj.end_time = item["end_time"]
                    obj.duration_seconds = item["duration"]
                    obj.final_disposition = item.get("disposition")
                    obj.max_frustration_score = item["max_frustration"]
                    if item.get("recording_consent") is not None:
                        obj.recording_consent = item["recording_consent"]

    # ---------- enqueue API (non-blocking) ----------
    def start_session(self, *, customer_id=None, subscription_id=None, msisdn=None,
                      livekit_room=None, recording_consent=None) -> str:
        """Open a call record; returns the session DB id (generated locally, FIFO-ordered)."""
        from persistence.util import to_uuid

        self._session_db_id = str(uuid.uuid4())
        self._start_time = datetime.now(UTC)
        self._enqueue("session_start", {
            "id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "msisdn": msisdn,
            "livekit_room": livekit_room,
            "recording_consent": recording_consent,
            "start_time": self._start_time,
            "channel": "voice",
        })
        return self._session_db_id

    def record_turn(self, speaker: str, text: str, active_agent=None, language=None, intent=None) -> None:
        """Append a turn (transcript PII-masked here, before it leaves the worker)."""
        if self._session_db_id is None:
            return
        self._turn_index += 1
        self._enqueue("turn", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "speaker": speaker,
            "active_agent": active_agent,
            "detected_language": language,
            "transcript_masked": self._masker.mask(text or ""),
            "detected_intent": intent,
        })

    def record_sentiment(self, score: float, label: str) -> None:
        """Append a sentiment sample for the current turn index."""
        if self._session_db_id is None:
            return
        self._enqueue("sentiment", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "score": score,
            "label": label,
        })

    def record_escalation(self, trigger: str, target: str, dossier: dict, customer_id=None) -> None:
        """Record an escalation case with the context dossier handed to the human/manager."""
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._enqueue("escalation", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "trigger": trigger,
            "target": target,
            "dossier": dossier,
        })

    def record_callback(self, *, customer_id=None, subscription_id=None, scheduled_time=None,
                        priority=1, preferred_window=None, reason=None) -> None:
        """Record a scheduled callback.

        ``preferred_window`` keeps the caller's own words ("demain matin") verbatim, so the advisor
        who picks the callback up sees what was actually asked for rather than only the fallback
        timestamp. ``scheduled_time`` still defaults to +24h when nothing could be parsed, which is
        a due-date for the queue, not a promise made to the caller.
        """
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._enqueue("callback", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "scheduled_time": scheduled_time or (datetime.now(UTC) + timedelta(hours=24)),
            "priority_level": priority,
            "preferred_window": (preferred_window or "")[:120] or None,
            "reason": (reason or "")[:60] or None,
        })

    def record_consent(self, *, granted: bool, language: str | None = None, customer_id=None) -> None:
        """Persist the recording-consent decision (crm.consent_records) + an audit entry (event 'consent')."""
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._queue.put_nowait({"kind": "consent", "row": {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "consent_type": "call_recording",
            "granted": granted,
            "language": language,
        }})

    def finish_session(self, *, disposition=None, max_frustration=0.0, recording_consent=None) -> None:
        """Close the call record (end time, duration, disposition, peak frustration)."""
        if self._session_db_id is None:
            return
        end = datetime.now(UTC)
        duration = int((end - (self._start_time or end)).total_seconds())
        self._queue.put_nowait({
            "kind": "session_finish",
            "session_db_id": uuid.UUID(self._session_db_id),
            "end_time": end,
            "duration": duration,
            "disposition": disposition,
            "max_frustration": max_frustration,
            "recording_consent": recording_consent,
        })

    def _enqueue(self, kind: str, row: dict) -> None:
        self._queue.put_nowait({"kind": kind, "row": row})

    async def aclose(self) -> None:
        """Signal the drain to finish and wait briefly for the queue to flush."""
        self._queue.put_nowait(None)
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except Exception:
                self._task.cancel()