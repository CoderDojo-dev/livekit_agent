"""P0-3/P1-1 - agent_activity() must report CALLER turns only.

Before P0-3 every row was a caller row, so the missing predicate was invisible.
This pins the intent so it cannot silently regress.
"""
from __future__ import annotations

import datetime
import uuid

from business_api.repositories import SupervisionRepository

from persistence.models.conversation import CallSession, Turn

_PROBE = "P03ProbeAgent"


def _seed(db_session) -> uuid.UUID:
    session_id = uuid.uuid4()
    db_session.add(
        CallSession(
            id=session_id,
            channel="voice",
            start_time=datetime.datetime.now(datetime.UTC),
        )
    )
    db_session.flush()
    for index, speaker in enumerate(("caller", "agent", "caller"), start=1):
        db_session.add(
            Turn(
                session_id=session_id,
                turn_index=index,
                speaker=speaker,
                active_agent=_PROBE,
                transcript_masked="x",
            )
        )
    db_session.flush()
    return session_id


def test_agent_activity_counts_caller_turns_only(db_session):
    _seed(db_session)

    report = SupervisionRepository(db_session).agent_activity(days=1)
    probe = next(row for row in report["agents"] if row["agent"] == _PROBE)

    assert probe["turns"] == 2, "agent rows must not inflate a column labelled 'Caller turns'"


def test_the_agent_row_really_exists(db_session):
    """Positive control for the test above.

    Without this, `turns == 2` would also pass if the agent row had never been
    inserted at all - the assertion would be measuring a failed write instead of a
    working filter. This also pins that ORDER BY turn_index is chronological.
    """
    session_id = _seed(db_session)

    detail = SupervisionRepository(db_session).session_detail(str(session_id))

    assert [turn["speaker"] for turn in detail["turns"]] == ["caller", "agent", "caller"]