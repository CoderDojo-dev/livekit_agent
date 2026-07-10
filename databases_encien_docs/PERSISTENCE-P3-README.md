# Persistence — P3: Conversation record, written off the voice path

The agent now keeps a durable, supervisable record of every call — sessions, turns, sentiment,
escalations, callbacks (spec §11) — written through a **non-blocking async writer** so persistence
never adds latency to voice-to-voice. This is the substrate the supervisor-dashboard reads in P4.

## What shipped (12 files)
- **Models** — `conversation.call_sessions`, `turns` (UNIQUE `session_id,turn_index,speaker`),
  `sentiment_samples`, `escalation_cases` (JSONB dossier), `callback_schedules`. DDL verified.
- **Migration `0003_conversation`** — creates the five tables + the `callback_schedules.updated_at`
  trigger.
- **`conversation/writer.py` — `ConversationWriter`**: callers enqueue plain dicts in constant time;
  a single background task drains the queue and does the actual Postgres writes **in a thread**
  (sync SQLAlchemy off the event loop). If the DB is unavailable, writes are logged and dropped —
  **the call is never affected**. Transcripts are **PII-masked in the worker** before they leave it.
- **Worker wiring (all off-path)** — `server.py` opens the call record at start and finalizes it on
  shutdown (end time, duration, peak frustration); `base_agent` records each caller turn + its
  sentiment from the existing turn hook; `escalation_tools` records the escalation case + dossier;
  `callback_schedule_task` records the scheduled callback. `SessionUserData` carries the writer +
  `session_db_id`.

## Design (why it's safe on a real-time path)
- **Enqueue-and-forget**: the hot path only does `queue.put_nowait(dict)`. No `await`, no DB.
- **One writer per call**; the session DB id is generated locally so turns can reference it
  immediately, and the **FIFO queue guarantees the session row is inserted before its turns**.
- **Fault-tolerant**: any write exception is swallowed + logged in the drain loop.

## Apply & run
```bash
export DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
( cd packages/persistence && alembic upgrade head )      # applies 0003
# the worker now needs the persistence package on its env:
cd apps/agent-worker && pip install -e ../../packages/persistence
# run the worker as usual (DATABASE_URL in its environment)
```

## Proving it (after a call)
```sql
SELECT id, msisdn, duration_seconds, final_disposition, max_frustration_score FROM conversation.call_sessions ORDER BY start_time DESC LIMIT 5;
SELECT turn_index, speaker, active_agent, transcript_masked FROM conversation.turns WHERE session_id = '<id>' ORDER BY turn_index;
SELECT turn_index, score, label FROM conversation.sentiment_samples WHERE session_id = '<id>' ORDER BY turn_index;
SELECT trigger, target, dossier FROM conversation.escalation_cases WHERE session_id = '<id>';
SELECT scheduled_time, priority_level, status FROM conversation.callback_schedules WHERE session_id = '<id>';
```
Offline (no DB): `tests/conversation` (3) + `tests/sentiment` (3) pass — enqueue sequencing, turn-index
increment, and **PII masking** are asserted without a loop or DB. The DB writes are exercised by a real
call against Postgres.

## Notes / honest caveats
- No Postgres in the build sandbox: verified offline what's verifiable (DDL render, mapper resolution,
  writer enqueue logic + masking, all pure suites). The conversation rows get their first real write
  when you run a call against `localhost:15432`; I'll fix fast if anything needs a tweak.
- **Agent-turn transcripts** are not captured yet (caller turns + sentiment are) — a one-hook add via
  `conversation_item_added` when you want both sides of the transcript.
- **`callback_schedules.scheduled_time`** is a +24h placeholder; the free-text window the caller speaks
  is kept in session state. A proper time-parse/queue is a small later refinement.
- **Next — P4:** domain **write** projections (`billing.payments`/`payment_plans`,
  `ocs.recharges`/`usage`, `sim.*`) written alongside `execution.action_ledger`, plus the ticketing
  mirror and notification log; then `reference.*` + business-api + the integrity job + Redis/Qdrant.
