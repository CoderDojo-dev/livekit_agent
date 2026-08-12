-- P1-2 backfill: give historical call sessions the disposition the database can prove.
--
-- Writes ONLY values derivable from persisted rows:
--   escalated -> an escalation case exists for the session
--   abandoned -> the caller never spoke (zero caller turns)
-- Sessions that ended without either signal stay NULL: whether they were resolved or dropped
-- depended on in-memory session state that no longer exists, and guessing would inflate the very
-- KPI this patch exists to make truthful.
--
-- Idempotent: every UPDATE is guarded by final_disposition IS NULL, so re-running is a no-op and
-- no row written by the agent is ever overwritten.
--
-- DELIBERATELY does NOT write to audit.audit_ledger. That chain's hashes are computed in Python by
-- PgAuditLedger under pg_advisory_xact_lock(8472); appending a row from raw SQL would produce an
-- entry whose hash does not chain, permanently breaking integrity verification. The record of this
-- operation is the results document plus the reversal list below.

\set ON_ERROR_STOP on

BEGIN;

-- Cutoff: only sessions that already existed before the P1-2 deploy. Replace with the deploy
-- timestamp recorded in the results document. This is what keeps the backfill off any session the
-- agent is writing right now.
\set cutoff '2026-08-12T07:22:38Z'

-- ---------------------------------------------------------------- reversal list (capture FIRST)
CREATE TEMP TABLE p1_2_backfilled AS
SELECT s.id
FROM conversation.call_sessions s
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz;

-- ---------------------------------------------------------------- before
SELECT 'before' AS phase, coalesce(final_disposition, 'NULL') AS disposition, count(*)
FROM conversation.call_sessions GROUP BY 1, 2 ORDER BY 2;

-- ---------------------------------------------------------------- 1. escalated (provable)
UPDATE conversation.call_sessions s
SET final_disposition = 'escalated'
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz
  AND EXISTS (SELECT 1 FROM conversation.escalation_cases e WHERE e.session_id = s.id);

-- ---------------------------------------------------------------- 2. abandoned (provable)
-- Runs second so an escalated session is never relabelled, matching _derive_disposition's own
-- precedence: escalation outranks everything.
UPDATE conversation.call_sessions s
SET final_disposition = 'abandoned'
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz
  AND NOT EXISTS (
        SELECT 1 FROM conversation.turns t
        WHERE t.session_id = s.id AND t.speaker = 'caller');

-- ---------------------------------------------------------------- after
SELECT 'after' AS phase, coalesce(final_disposition, 'NULL') AS disposition, count(*)
FROM conversation.call_sessions GROUP BY 1, 2 ORDER BY 2;

-- Reversal list: save this output. It is the exact set to reset if the backfill must be undone.
SELECT 'reversal_id' AS kind, id FROM p1_2_backfilled ORDER BY id;

-- Safety assertion: nothing outside the CHECK vocabulary can have been written.
SELECT 'ILLEGAL VALUE PRESENT' AS alarm, final_disposition, count(*)
FROM conversation.call_sessions
WHERE final_disposition IS NOT NULL
  AND final_disposition NOT IN ('resolved', 'escalated', 'dropped', 'abandoned')
GROUP BY 2;

-- ROLLBACK for the dry run. Change to COMMIT only after reviewing the before/after counts.
ROLLBACK;
