# P0-3 — Persist Agent Turns (+ the P1-1 metric correction that must ship with it)

**Branch:** `version_83`
**Prerequisite:** P0-1 green (`verify_p0_1.sh` 20/20) and P0-2 applied.
**Scope:** one backend behaviour change in the agent worker, one query correction in business-api,
two new offline tests. **Zero frontend changes.**
**Rebuild required:** yes, both `agent-worker` and `business-api` (their Dockerfiles bake source).

---

## §1 What P0-3 is, and why it is smaller than it looks

Every stored conversation in this platform is a **monologue**. All 490 rows in
`conversation.turns` carry `speaker = 'caller'`. The agent's half of every call has never been
written down. A supervisor opening a call transcript sees what the customer said and must infer
what the agent replied.

The interesting part is *why*. This is not a missing mechanism. Read the composition root:

```python
@session.on("conversation_item_added")
def _on_conversation_item_added(event: ConversationItemAddedEvent):
    item = event.item
    if not isinstance(item, ChatMessage):
        return
    text = item.text_content
    if not text:
        return
    if item.role == "user":
        logger.info("🎤 Caller: %s", text)
    elif item.role == "assistant":
        logger.info("🤖 Agent: %s", text)
```

The agent's reply text is **already captured, already in a variable, already filtered for
emptiness — and then thrown into a log line and discarded.** P0-3 is not "build a way to persist
agent turns." It is "stop discarding the thing you are already holding."

That is why this patch is one call site. The master instruction's requirement — *persist via the
existing writer, do not introduce a second mechanism* — is satisfied for free, because the
existing writer is already open, already started, and already in lexical scope at that exact line.

### 1.1 What ships with it, and why it cannot ship later

`agent_activity()` counts `conversation.turns` rows with **no `speaker` predicate**. Today that is
accurate, because every row is a caller row. FEATURE_20 relabelled that column **"Caller turns"**
on the strength of that fact.

The moment the first agent turn lands, that label becomes a lie and the number roughly doubles —
silently, with no error, on a dashboard someone is using to judge agent behaviour. The metric fix
is therefore **not a follow-up**. It is part of this patch. Shipping P0-3 alone would knowingly
introduce a wrong number into a supervision console.

---

## §2 Coverage disclosure — what I read for this patch

Every claim below is from the literal file at `version_83`. Blob SHAs recorded so you can prove I
read the same bytes you are about to edit.

| File | Blob SHA | Why it mattered |
| --- | --- | --- |
| `apps/agent-worker/src/server.py` | `b03539f6` | the hook already exists; `writer`/`user_data`/`session` all in scope |
| `apps/agent-worker/src/conversation/writer.py` | `fbfea025` | `record_turn` semantics, the single `_turn_index`, queue/drain safety |
| `apps/agent-worker/src/agents/base_agent.py` | `839146b2` | the only known `record_turn` caller; sentiment ordering |
| `packages/persistence/src/persistence/models/conversation.py` | `ec4592ad` | `CHECK speaker IN ('caller','agent')`, `UNIQUE(session_id, turn_index, speaker)` |
| `apps/business-api/src/business_api/repositories.py` | `0cbf037d` | `agent_activity`, `session_detail`, `session_list`, `system_overview` |
| `Frontend/admin_dashboard/src/components/nexus/transcript.tsx` | `af518278` | already renders both speakers |
| `Frontend/admin_dashboard/src/lib/nexus/call-view.ts` | `9d377259` | `turnKey` = `index-speaker`; `sentimentByIndex` sparse by design |
| `Frontend/admin_dashboard/src/lib/api/sessions.server.ts` | `fce2d7e2` | `TranscriptTurnRow.speaker` already typed |
| `apps/agent-worker/src/session/session_state.py` | `a852e491` | `SessionUserData` fields; `conversation_writer` |
| `apps/agent-worker/src/providers/_resilience.py` | `8a854b84` | `session.say()` apology — an agent utterance outside any caller turn |

**External API verification.** Two LiveKit APIs are used that are not already exercised in this
repo's own code. Both were confirmed against the framework, not assumed:

- `AgentSession.current_agent -> Agent` — confirmed in the LiveKit Python API reference and in
  `livekit-agents/livekit/agents/voice/agent_session.py`. It **raises `RuntimeError` when no agent
  is running**, which is why the code below guards it.
- `ChatMessage.interrupted` — confirmed present (used in framework issue reports). Not written by
  this patch; noted in §6.3 as a deliberate omission.

`ConversationItemAddedEvent`, `ChatMessage`, `item.role`, `item.text_content` need no external
verification — `server.py` already imports and uses all four.

**Not read:** `providers/session_factory.py`, `tools/session_flow_tools.py`, the handoff tools, and
the seven `apps/agent-worker/tests/` subdirectories. None are edited. The pre-flight gates in §0
convert the two assumptions this creates into checks rather than beliefs.

---

## §0 Pre-flight gates

Run all of these before editing. Each has a STOP condition. Do not "adapt around" a STOP — report it.

### 0.1 Baseline

```bash
git rev-parse --abbrev-ref HEAD                     # expect: version_83
bash scripts/verify_p0_1.sh                          # expect: 20/20
python -m pytest apps/business-api/tests -q          # record the number; must not fall later
```

### 0.2 GATE — `record_turn` has exactly one caller today

This patch adds the second caller. If there is already an unexpected third, my double-write
analysis in §3.4 is incomplete.

```bash
git grep -n "record_turn" -- apps/ packages/
```

**Expect exactly two hits:** the definition in `conversation/writer.py`, and the call in
`agents/base_agent.py` (which passes `speaker="caller"`).
**STOP** if any other call site exists — report it before continuing.

### 0.3 GATE — no other `conversation_item_added` handler

```bash
git grep -n "conversation_item_added" -- apps/
```

**Expect exactly one** handler, in `server.py`. **STOP** otherwise: two handlers would double-write.

### 0.4 GATE — the data really is caller-only today

```bash
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "SELECT speaker, count(*) FROM conversation.turns GROUP BY speaker ORDER BY speaker;"
```

**Expect a single row:** `caller | 490` (or higher if calls have run since).
**STOP if an `agent` row already exists** — then agent turns are being written by something I did
not find, and §0.2/§0.3 missed it.

Record this number. It is the before-value for the §8 proof.

### 0.5 GATE — the worker test directory

```bash
ls apps/agent-worker/tests/conversation/
```

The new worker test in §7.1 goes here. If this directory does not exist, **STOP** — do not invent
a different location.

### 0.6 Lint baselines (record, do not fix)

```bash
ruff check apps/agent-worker/src | tail -1     # known: 16, all pre-existing
ruff check apps/business-api/src/business_api/main.py | tail -1   # known: 7
```

P0-2 recorded `ruff check .` repo-wide at **147**. That is P1-2/P1-3 territory, untouched here.
The only requirement is that **this patch adds none**.

---

## §3 The one real design decision: how agent turns are numbered

This is the only part of P0-3 where a wrong choice causes silent data loss, so it gets a full
section rather than a line of code.

### 3.1 What the schema permits

```python
UniqueConstraint("session_id", "turn_index", "speaker", name="session_turn_speaker")
```

`speaker` is part of the unique key. That is only *necessary* if the same `turn_index` can appear
twice under different speakers. So the schema author anticipated **paired numbering**: caller turn
N and agent turn N are one exchange.

The frontend says the same thing, independently:

```ts
/** F5 — index alone is NOT unique; speaker disambiguates caller/agent at the same index. */
export function turnKey(turn: TranscriptTurnRow): string {
  return `${turn.index}-${turn.speaker}`;
}
```

Two separate artifacts, written at different times, both encode the same expectation.

### 3.2 Why I am not implementing paired numbering anyway

Paired numbering is the *inferred intent*, and it is still the wrong choice, for two concrete
reasons that only appear at runtime.

**Reason 1 — it silently drops rows when one caller turn produces two agent utterances.**
LiveKit can emit more than one assistant item per user turn (a spoken preamble before a tool call,
then the final answer). `_resilience.py` also calls `session.say()` for the reconnect apology,
which is an agent utterance that belongs to **no** caller turn at all:

```python
self._apology_task = asyncio.create_task(self.session.say(_APOLOGY.get(_code, _APOLOGY["fr"])))
```

Under paired numbering, the second assistant item of a turn collides on
`(session_id, turn_index, 'agent')`. And the writer's failure mode is **to swallow it**:

```python
except Exception as exc:
    logger.warning("conversation write dropped (%s): %s", (item or {}).get("kind"), exc)
```

A dropped write, logged at WARNING, in a background drain task. That is precisely the class of
silent data loss this patch exists to eliminate. Choosing a numbering scheme that reintroduces it
would be self-defeating.

**Reason 2 — it makes transcript ordering undefined.**
`session_detail` orders by `Turn.turn_index` alone. With two rows sharing an index, the order
between them is whatever Postgres returns. Fixing that needs a tiebreak, and the obvious one is
wrong: `ORDER BY turn_index, speaker` puts **`'agent'` before `'caller'`** alphabetically, i.e. the
reply above the question, on every exchange.

### 3.3 The decision

**Agent turns take the next value of the existing monotonic counter.** Caller `#1`, agent `#2`,
caller `#3`, agent `#4`.

This is chosen because it is the option that requires **no change to `writer.py` at all**.
`record_turn` already increments `self._turn_index` on every call and already accepts `speaker` as
its first parameter. Calling it with `speaker="agent"` is using the existing writer exactly as
written. Consequences, all verified against the files in §2:

| Property | Result under monotonic numbering |
| --- | --- |
| Unique constraint | can never collide — `turn_index` is unique per session on its own |
| `ORDER BY turn_index` in `session_detail` | already total and already chronological; no change needed |
| `turnKey` in the UI | `1-caller`, `2-agent`, … still unique; the F5 comment remains a correct safety net |
| `sentimentByIndex` | caller turns keep their own index, so sentiment still lands on the caller line |
| Multiple agent utterances per exchange | each gets its own index; nothing is dropped |
| `session.say()` outside a caller turn | recorded normally |
| The 490 existing rows | untouched and still valid — they are simply a contiguous run |

The `speaker` column in the unique key stays useful as a safety net. It is simply no longer
*load-bearing*.

### 3.4 Why this cannot double-write the caller side

`conversation_item_added` fires for **both** roles. Caller turns are already written by
`base_agent.on_user_turn_completed`. Therefore this patch adds a write **only inside the
`elif item.role == "assistant"` branch**. The `if item.role == "user"` branch is left exactly as
it is — logging only. Gate §0.2 confirms `base_agent` remains the sole caller-turn writer.

### 3.5 Why sentiment indexing is unaffected

`record_sentiment` uses whatever `self._turn_index` currently is. In `base_agent`:

```python
writer.record_turn(speaker="caller", ...)
writer.record_sentiment(score=score, label=sentiment_label(score))
```

These are two adjacent synchronous statements with **no `await` between them**, so no other
coroutine — including the agent-turn handler — can run in between. The sentiment sample therefore
always carries the caller's index. This is not luck; it is a property of the asyncio scheduler,
and it is why the ordering is safe without a lock.

---

## §4 Change 1 — persist the agent turn (`server.py`)

**File:** `apps/agent-worker/src/server.py`
**Edit type:** replace the two-line `assistant` branch. No imports change. No other line moves.

### 4.1 oldStr (byte-exact — copy from the file, verify the emoji survives your editor)

```python
        elif item.role == "assistant":
            logger.info("🤖 Agent: %s", text)
```

### 4.2 newStr

```python
        elif item.role == "assistant":
            logger.info("🤖 Agent: %s", text)
            # P0-3 - persist the agent half of the transcript. The text is already in
            # hand here; before this it was logged and discarded, so every stored
            # conversation was a monologue. Same writer, same queue, same table and
            # the same enqueue-only contract as the caller side: nothing here touches
            # the voice path, and a DB outage still degrades to a dropped row.
            try:
                persona = type(session.current_agent).__name__
            except Exception:  # noqa: BLE001 - no active agent yet; attribution is optional
                persona = None
            writer.record_turn(
                speaker="agent",
                text=text,
                active_agent=persona,
                language=getattr(user_data, "language", None),
            )
```

### 4.3 Why each line is what it is

| Line | Justification |
| --- | --- |
| placed inside `elif ... "assistant"` | the `user` branch would double-write (§3.4) |
| after the existing `logger.info` | the log line is existing behaviour; it is preserved, not replaced |
| `speaker="agent"` | the only other value permitted by `CHECK speaker IN ('caller','agent')` |
| `text=text` | reuses the variable the handler already computed and already null-guarded via `if not text: return` |
| `type(session.current_agent).__name__` | byte-identical attribution to the caller path, which stores `type(self).__name__` |
| wrapped in `try/except` | `current_agent` **raises `RuntimeError`** when no agent is running; attribution must never break a transcript write |
| `persona = None` on failure | `active_agent` is nullable, and `transcript.tsx` already renders `{turn.agent ? <Token/> : null}` |
| `getattr(user_data, "language", None)` | copied verbatim from the caller path in `base_agent.py` |
| no `intent=` | the caller path does not pass it either; inventing intent classification is out of scope |

### 4.4 Scope proof

`writer`, `user_data` and `session` are all locals of `entrypoint`, assigned **before** the handler
is defined (`session` at the `build_agent_session` line, `user_data` just above it, `writer` at
`writer = _open_conversation(ctx, user_data)`). The handler closes over all three. No new
parameter, no global, no import.

The handler is a plain `def`, not `async def`. `record_turn` is synchronous and ends in
`self._queue.put_nowait(...)`. Calling it from a sync event handler is correct and non-blocking —
this is the same contract `base_agent` already relies on.

### 4.5 PII

No new exposure. `record_turn` masks every transcript through `self._masker.mask(text or "")`
before it leaves the worker, and agent turns go through that identical line. This matters more
than it may appear: the agent frequently *reads back* a caller's number or reference, so the agent
side needs masking just as much as the caller side. It gets it automatically.

---

## §5 Change 2 — keep "Caller turns" true (`repositories.py`)

**File:** `apps/business-api/src/business_api/repositories.py`, method `agent_activity`.
**Why it is in this patch and not the next one:** §1.1.

### 5.1 oldStr (byte-exact)

```python
            .join(CallSession, CallSession.id == Turn.session_id)
            .where(CallSession.start_time >= since)
            .where(Turn.active_agent.isnot(None))
            .where(Turn.active_agent != "")
```

### 5.2 newStr

```python
            .join(CallSession, CallSession.id == Turn.session_id)
            .where(CallSession.start_time >= since)
            # P0-3/P1-1 - count CALLER turns only. Before P0-3 every row in
            # conversation.turns was a caller row, so this predicate was a no-op and
            # its absence was invisible. The moment agent turns persist, omitting it
            # would roughly double the number under a column labelled "Caller turns".
            .where(Turn.speaker == "caller")
            .where(Turn.active_agent.isnot(None))
            .where(Turn.active_agent != "")
```

This is an additive predicate on a read-only query. It removes no column, changes no return shape,
and no caller signature moves. `session_count` narrows in the same honest direction: a session
where the persona only ever spoke is no longer counted as caller activity.

### 5.3 GATE — the other two counters that change meaning

Two more places count `Turn` rows with no speaker predicate. Unlike `agent_activity`, I have **not
read the components that render them**, so I will not tell you they are wrong. Read the label
first, then decide. This is the rule from your own §1.4.

| Location | Field | What it becomes after P0-3 |
| --- | --- | --- |
| `repositories.py::session_list` | `turn_count` | total turns per call, both speakers |
| `repositories.py::system_overview` | `metrics.total_turns` | total turns platform-wide, both speakers |

```bash
git grep -n "turn_count" -- Frontend/admin_dashboard/src
git grep -n "total_turns" -- Frontend/admin_dashboard/src
```

**Decision rule — apply it literally:**

- If the rendered label says **"Turns"**, **"Total turns"** or similar → **change nothing.** The
  number is now more accurate than it was, because a conversation genuinely has two sides.
- If the rendered label says **"Caller"**, **"Customer"**, or implies one speaker → report it and
  apply the same `.where(Turn.speaker == "caller")` predicate there too.

Either way, **write the label you found into the completion report.** A number whose meaning
changes silently at a date boundary is exactly the defect FEATURE_20 was raised to fix.

### 5.4 A property of the data you should know before reading any chart

All existing rows are caller-only. Every per-call turn total therefore has a **discontinuity at
the deploy timestamp**: calls before it count one side, calls after it count two. No backfill is
possible — the agent's historical words were never recorded and cannot be recovered. Any trend
line that crosses this date is comparing two different measurements. Record the deploy time in the
completion report so whoever reads a chart later can see the seam.

---

## §6 What is deliberately NOT changed

| File | Why untouched |
| --- | --- |
| `conversation/writer.py` | §3.3 — `record_turn` already does exactly what is needed. Zero edits. |
| `agents/base_agent.py` | the caller path is correct; touching it risks the 490-row-per-month path for no gain |
| `models/conversation.py` | `speaker` already permits `'agent'`. **No migration. No alembic revision.** |
| `transcript.tsx`, `call-view.ts`, `sessions.server.ts` | already correct — see §6.1 |
| `pyproject.toml`, `package.json` | no dependency added |

### 6.1 The frontend genuinely needs nothing

This is a claim I am obliged to justify by reading, not assume. From `transcript.tsx`:

- `const isCaller = turn.speaker === "caller";` — the speaker split already exists.
- `{isCaller ? "Caller" : "Agent"}` — the agent label already exists.
- `const mood = isCaller ? byIndex.get(turn.index) : undefined;` under the comment
  *"F5 — sentiment measures the CALLER. Never paint the agent's line with it."*
- `{turn.agent ? <Token mono={false}>{turn.agent}</Token> : null}` — null-safe attribution.
- `turn.text?.trim() || "(no transcript captured)"` — null-safe text.
- `key={turnKey(turn)}` where `turnKey` is `` `${turn.index}-${turn.speaker}` `` — collision-safe.

And `TranscriptTurnRow.speaker` is already typed `string` in `sessions.server.ts`. The UI has been
waiting for this data. The first agent turn will simply appear, styled `text-ink-3` against the
caller's `text-ink-2`, with no sentiment dot. **No design-system decision is required, which is
why this patch adds no colours, no components and no tokens.**

### 6.2 One consequence worth stating plainly

Every historical call will still render as a monologue forever. Only calls placed **after** this
deploy will show both sides. That is not a defect in the patch; it is the cost of the data never
having been written. Do not let anyone read an old transcript and conclude P0-3 failed.

### 6.3 `interrupted` is deliberately not stored

`ChatMessage` exposes `interrupted`, which marks a reply the caller talked over — generated in
full, spoken only in part. Storing it would need a new column, therefore a migration, therefore
scope this patch does not have. The consequence is honest and should be recorded: **an interrupted
agent turn is stored as though it were fully spoken.** Logged as a P1-2 candidate, not fixed here.

---

## §7 Tests

Both are offline and deterministic — no network, no LiveKit, no sleeping. That is deliberate:
P1-3 is about getting `apps/agent-worker` into CI, and §7.1 must be a test that can actually run
there.

### 7.1 New — `apps/agent-worker/tests/conversation/test_writer_agent_turns.py`

The enqueue API is synchronous (`put_nowait`), so the queue can be drained and inspected with no
event loop and no database. Reading `writer._queue` is deliberate: it is the seam between the
voice path and the DB, and it is the only place the numbering rule is observable without Postgres.

```python
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
```

> `start_session()` imports `persistence.util`. The worker environment installs
> `./packages/persistence` (Dockerfile line 8 and `make install`), so this resolves. If it does
> not resolve in your shell, that is an environment problem — report it, do not stub the import.

### 7.2 New — `apps/business-api/tests/test_agent_activity_speaker.py`

Uses the existing `db_session` fixture. Import style is `from conftest import ...` if you need a
fixture helper — never `from tests.conftest import ...` (the P0-1 convention, deviation 2).

```python
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
```

That second test is the lesson from P0-1 case 20 applied here: **a negative assertion is worthless
until something proves the thing it is filtering actually exists.**

---

## §8 Verification

### 8.1 Static

```bash
ruff check apps/agent-worker/src | tail -1                 # must equal the §0.6 baseline (16)
ruff check apps/business-api/src/business_api | tail -1    # must add nothing
ruff check apps/agent-worker/tests/conversation/test_writer_agent_turns.py
ruff check apps/business-api/tests/test_agent_activity_speaker.py
git diff --stat                                            # exactly the §13 manifest, nothing else
```

### 8.2 Tests, before any container work

```bash
python -m pytest apps/agent-worker/tests/conversation -q
python -m pytest apps/business-api/tests -q                # count increases and is green
```

### 8.3 Rebuild — both images

Both Dockerfiles bake source. A `restart` will run the old code and produce a green-looking result
that proves nothing.

```bash
docker compose -p docker-compose \
  -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml \
  up -d --build agent-worker business-api
```

### 8.4 Proof the write path works end to end (mandatory)

This runs the real writer against the real database **inside the worker container**, which is the
part that could genuinely fail — the `CHECK speaker IN ('caller','agent')` constraint has never
had an `'agent'` row tested against it in this deployment.

```bash
docker exec -i docker-compose-agent-worker-1 python - <<'PY'
import asyncio
from conversation.writer import ConversationWriter

async def main():
    w = ConversationWriter()
    w.start()
    sid = w.start_session(msisdn="+21600000000")
    w.record_turn(speaker="caller", text="P0-3 probe caller", active_agent="P03Probe")
    w.record_turn(speaker="agent", text="P0-3 probe agent", active_agent="P03Probe")
    await w.aclose()
    print("session", sid)

asyncio.run(main())
PY
```

Then confirm both sides landed:

```bash
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "SELECT speaker, turn_index, active_agent FROM conversation.turns
   WHERE active_agent = 'P03Probe' ORDER BY turn_index;"
```

**Expect two rows: `caller|1` and `agent|2`.** If the agent row is absent, the CHECK constraint or
the drain silently rejected it — check the worker log for `conversation write dropped`.

Clean up the probe rows afterwards (they would otherwise pollute `agent_activity`):

```bash
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "DELETE FROM conversation.turns WHERE active_agent = 'P03Probe';"
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "DELETE FROM conversation.call_sessions WHERE id NOT IN
     (SELECT DISTINCT session_id FROM conversation.turns) AND msisdn = '+21600000000';"
```

> Never `TRUNCATE`. Hazard H-2: a previous session permanently lost the 34th `advisor_shifts` row
> that way, and it is not recoverable.

### 8.5 Proof the hook actually fires on real calls

You do **not** need a live LiveKit call to establish this, and the environment's DNS flapping to
`livekit.cloud` makes one unreliable. The branch this patch extends already logs on every real
call today:

```bash
docker logs docker-compose-agent-worker-1 2>&1 | grep -c "🤖 Agent:"
```

A non-zero count from **before** this patch is the evidence that
`elif item.role == "assistant"` executes in production. P0-3 adds a write immediately beside a
log line that is already proven to run. Record the count in the completion report.

If a real call *is* possible, the stronger proof is the §0.4 query re-run afterwards: a new
`agent` row appears, and the transcript at `/sessions/<id>` shows alternating speakers.

### 8.6 Nothing else broke

```bash
bash scripts/verify_p0_1.sh          # must still be 20/20
bash scripts/verify_p0_2.sh          # must still be 9/9
```

The worker rebuild touches the machine-identity path from P0-1, so `verify_p0_1.sh` is a genuine
regression net here, not a formality.

---

## §9 Apply order

1. §0 gates — all of them. STOP on any failure.
2. §7.1 + §7.2 tests **first**. §7.1 must pass immediately (it tests the writer as it already is).
   §7.2's first test must **fail** before §5 is applied — that failure is the proof the predicate
   is doing work. Record it.
3. §5 — `repositories.py`. Re-run §7.2: now green.
4. §4 — `server.py`.
5. §8.1 static, §8.2 tests.
6. §8.3 rebuild both.
7. §8.4, §8.5, §8.6.
8. §5.3 label gate — grep, decide, record.

Step 2's deliberate red is the same discipline as P0-2's guard-before-deletion: a test that was
never seen failing has not been shown to test anything.

---

## §10 Rollback

```bash
git checkout -- apps/agent-worker/src/server.py \
                apps/business-api/src/business_api/repositories.py
rm -f apps/agent-worker/tests/conversation/test_writer_agent_turns.py \
      apps/business-api/tests/test_agent_activity_speaker.py
# then rebuild both images again
```

No migration, no schema change, no data migration, no dependency change. Agent rows already written
before a rollback stay in the table and remain valid — the schema always allowed them.

---

## §11 Impact analysis

| Area | Impact |
| --- | --- |
| Voice path latency | none. `record_turn` is `put_nowait` on an in-memory queue; the DB write happens in a background thread. This is the writer's whole design premise. |
| DB write volume | roughly **2×** on `conversation.turns`. Append-only table, indexed on `session_id`. At this platform's volume (490 rows total to date) this is not a capacity question. |
| DB outage behaviour | unchanged — the drain logs and drops; the call is never affected. |
| LiveKit / agent behaviour | none. No instruction, tool, persona or handoff is touched. |
| P0-1 machine identity | untouched, but re-proved by §8.6 because the worker image is rebuilt. |
| Transcript UI | agent lines start appearing. No code change, no style change. |
| `agent_activity` | now correctly caller-only; numbers stay comparable across the deploy. |
| `turn_count` / `total_turns` | meaning changes — gated in §5.3. |
| Historical data | untouched. Not backfillable. |
| CI | two new offline test files. |

**The one prod-visible surprise:** per-call turn counts jump at the deploy timestamp (§5.4).

---

## §12 Confidence

**High on the mechanism, medium on one number.**

High, because the hook, the writer, the schema's `'agent'` value and the UI's speaker handling all
already exist and were read byte-for-byte. This patch adds one call and one `WHERE` clause. The
LiveKit APIs it relies on were verified against the framework rather than assumed, and the one
that can raise (`current_agent`) is guarded.

Medium on §5.3, because I have not read the components that render `turn_count` and `total_turns`
and I am not going to tell you they are fine without reading them. That is why §5.3 is a gate with
a decision rule rather than an edit.

**Weakest point, stated plainly:** I cannot prove from here that LiveKit emits exactly one
`conversation_item_added` assistant item per agent utterance in 1.6.5. That is why the numbering
scheme in §3.3 was chosen to be correct **regardless** of how many it emits, and why §7.1 has a
test for the two-utterance case specifically.

---

## §13 File manifest — authoritative

**Modified (2):**

| File | Change |
| --- | --- |
| `apps/agent-worker/src/server.py` | §4 — write the agent turn in the existing `assistant` branch |
| `apps/business-api/src/business_api/repositories.py` | §5 — `.where(Turn.speaker == "caller")` in `agent_activity` |

**Created (2):**

| File |
| --- |
| `apps/agent-worker/tests/conversation/test_writer_agent_turns.py` |
| `apps/business-api/tests/test_agent_activity_speaker.py` |

**Explicitly NOT touched:** `writer.py`, `base_agent.py`, `models/conversation.py`, any alembic
revision, any frontend file, `pyproject.toml`, `package.json`, `status.ts`, `.env` / `.env.example`.

If your diff contains a file not on this list, stop and report it.

---

## §14 Completion report to return

```
P0-3 RESULTS

Gates (§0)
- 0.2 record_turn call sites found: <paste the grep output>
- 0.3 conversation_item_added handlers: <count>
- 0.4 speaker counts BEFORE:  caller=<n>  agent=<n>
- 0.5 tests/conversation/ exists: yes/no
- 0.6 ruff baselines: worker=<n>  main.py=<n>

Step 2 deliberate red
- test_agent_activity_counts_caller_turns_only failed before §5: yes/no  (<observed value>)

Changes
- server.py assistant branch: applied
- repositories.py agent_activity predicate: applied
- two test files added

Verification
- pytest worker conversation: green
- pytest business-api: increased and green
- ruff: no new errors (worker <n>, business-api <n>)
- §8.4 probe rows: caller|1 and agent|2 observed / not observed
- §8.4 probe rows cleaned up: yes/no
- §8.5 pre-existing "🤖 Agent:" log lines: <count>
- verify_p0_1.sh: 20/20
- verify_p0_2.sh: 9/9
- deploy timestamp (the seam in §5.4): <UTC time>

§5.3 label gate
- turn_count rendered label: "<exact text>"   -> changed / left as is
- total_turns rendered label: "<exact text>"  -> changed / left as is

Real call, if one was possible
- new agent row observed: yes / no / not attempted
- transcript shows alternating speakers: yes / no / not attempted

Deviations
- <anything that differed from this document, with the reason>

Anything found that this document did not predict
- <...>
```

No test totals are asserted anywhere in this document. "Increases and is green" is the contract —
I have miscounted a checklist four times and will not do it a fifth.

---

## §15 Handoff

**P0 is complete after this.** Remaining order: P1-1 (largely absorbed here — what is left is
auditing the *other* metrics against what they claim), P1-2, P1-3, P2-1, P2-2.

Carried forward, created or confirmed by this patch:

1. **`interrupted` is not stored** (§6.3) — an interrupted reply looks fully spoken. P1-2.
2. **`turn_count` / `total_turns`** — whatever §5.3 decides, record it. P1-1.
3. **The deploy seam** (§5.4) — per-call turn totals are not comparable across it.
4. **`apps/agent-worker` is still absent from the CI `test` job.** §7.1 was written offline and
   deterministic precisely so P1-3 can add `apps/agent-worker` to that loop and have it pass.
5. **`ruff check .` = 147 repo-wide** (P0-2 measurement) — the CI `lint` job runs exactly that
   command, so it is very likely red on `main` today. P1-3.
6. **The `docker-build` matrix** still points at `services/${{ matrix.service }}/Dockerfile` for
   three apps that live under `apps/`. P1-3.
7. **`final_disposition` is NULL on all 129 sessions** — so `kpis()` reports 0% resolved and 0%
   escalated, and `dispositionKey(null)` renders every historical call as "In progress". Now that
   transcripts are complete, this is the next thing that makes the console look broken. P1-2.
8. **`apps/supervisor-dashboard/src/api.ts`** — still the last front-app source sending `X-Role`;
   its calls 401 since P0-1. Rewire or delete. P1-2.
