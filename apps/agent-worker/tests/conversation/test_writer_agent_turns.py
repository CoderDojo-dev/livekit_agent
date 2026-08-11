"""P0-3 - the writer must accept an agent turn and number it without colliding.

Offline and deterministic: no database, no event loop, no LiveKit. ConversationWriter's
enqueue API is synchronous by design, so the queue is drained directly.
"""
from __future__ import annotations

from conversation.writer import ConversationWriter


def _open() -> ConversationWriter:
    writer = ConversationWriter()
    writer.start_session(msisdn="+21600000000")
    return writer


def _drain(writer: ConversationWriter) -> list[dict]:
    items: list[dict] = []
    while not writer._queue.empty():
        items.append(writer._queue.get_nowait())
    return items


def _turns(items: list[dict]) -> list[dict]:
    return [item["row"] for item in items if item["kind"] == "turn"]


def test_agent_turn_is_accepted_and_marked_agent():
    writer = _open()
    writer.record_turn(speaker="caller", text="bonjour")
    writer.record_turn(speaker="agent", text="bonjour, comment puis-je vous aider")

    assert [turn["speaker"] for turn in _turns(_drain(writer))] == ["caller", "agent"]


def test_turn_keys_are_unique_within_a_session():
    """Pins the UNIQUE(session_id, turn_index, speaker) constraint at the source."""
    writer = _open()
    for _ in range(3):
        writer.record_turn(speaker="caller", text="question")
        writer.record_turn(speaker="agent", text="reponse")

    turns = _turns(_drain(writer))
    keys = [(t["session_id"], t["turn_index"], t["speaker"]) for t in turns]
    assert len(keys) == len(set(keys))
    assert [t["turn_index"] for t in turns] == [1, 2, 3, 4, 5, 6]


def test_two_agent_utterances_in_one_exchange_do_not_collide():
    """A spoken preamble before a tool call, or the reconnect apology from session.say().

    Under paired numbering this is the case that silently loses a row, because the
    writer swallows the IntegrityError and only logs a warning.
    """
    writer = _open()
    writer.record_turn(speaker="caller", text="question")
    writer.record_turn(speaker="agent", text="un instant")
    writer.record_turn(speaker="agent", text="voici la reponse")

    indexes = [t["turn_index"] for t in _turns(_drain(writer))]
    assert len(indexes) == len(set(indexes))


def test_sentiment_still_binds_to_the_caller_turn():
    """Sentiment measures the caller; an agent turn must not shift its index."""
    writer = _open()
    writer.record_turn(speaker="caller", text="je suis furieux")
    writer.record_sentiment(score=-0.8, label="angry")
    writer.record_turn(speaker="agent", text="je comprends votre frustration")

    items = _drain(writer)
    caller = next(t for t in _turns(items) if t["speaker"] == "caller")
    sentiment = next(item["row"] for item in items if item["kind"] == "sentiment")
    assert sentiment["turn_index"] == caller["turn_index"]


def test_agent_transcript_is_masked_before_it_leaves_the_worker():
    """The agent reads numbers back to the caller, so its side needs masking too.

    Asserts the stored value is the masker's output rather than the raw text, without
    asserting what the masker does - that is pii-shield's contract, not this test's.
    """
    writer = _open()
    spoken = "votre reference est 21612345678"
    writer.record_turn(speaker="agent", text=spoken)

    row = _turns(_drain(writer))[0]
    assert row["transcript_masked"] == writer._masker.mask(spoken)