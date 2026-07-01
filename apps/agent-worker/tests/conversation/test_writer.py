"""Offline tests for ConversationWriter enqueue logic + sentiment labels (no loop, no DB).

The actual Postgres writes are integration-tested on the developer machine."""
from __future__ import annotations

from conversation.writer import ConversationWriter, sentiment_label


def _drain_queue(writer):
    items = []
    while not writer._queue.empty():
        items.append(writer._queue.get_nowait())
    return items


def test_sentiment_label_mapping() -> None:
    assert sentiment_label(-1.0) == "angry"
    assert sentiment_label(-0.4) == "negative"
    assert sentiment_label(0.0) == "neutral"
    assert sentiment_label(0.5) == "positive"


def test_turns_increment_and_mask_pii() -> None:
    writer = ConversationWriter()  # not started -> no drain, inspect the queue directly
    writer.start_session(msisdn="+21620155320", recording_consent=True)
    writer.record_turn("caller", "my number is +21620155320", active_agent="TriageAgent", language="fr")
    writer.record_turn("caller", "still broken", language="fr")
    items = _drain_queue(writer)
    assert [i["kind"] for i in items] == ["session_start", "turn", "turn"]
    assert items[1]["row"]["turn_index"] == 1
    assert items[2]["row"]["turn_index"] == 2
    assert "+21620155320" not in items[1]["row"]["transcript_masked"]  # masked before leaving the worker


def test_no_writes_before_session_started() -> None:
    writer = ConversationWriter()
    writer.record_turn("caller", "hello")  # ignored: no session opened
    assert writer._queue.empty()