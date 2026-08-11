# Version 85 — P0-3 persist agent turns + P1-1 metric correction

> **Base branch:** `version_84` (`257f66d`)
> **Commits:** 1 (P0-3 lot)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none
> **Rebuild:** required — agent-worker AND business-api (their Dockerfiles bake source)

---

## Containers & SDK

| Item               | Change                          |
|--------------------|---------------------------------|
| New containers     | None                            |
| livekit-agents SDK | `1.6.5` (unchanged)             |
| livekit-server     | `v1.8.4` (unchanged)            |
| Docker Compose     | Unchanged                       |
| agent-worker image | **Rebuild required** (`server.py` persists agent turns) |
| business-api image | **Rebuild required** (`agent_activity` query corrected) |

---

## What's New in This Branch

### The problem

Every stored conversation was a **monologue**: all 490 rows in `conversation.turns` carried
`speaker = 'caller'`. The agent's half of every call was logged and discarded — a supervisor
opening a transcript saw only what the customer said and had to infer the replies. The "Caller
turns" dashboard metric was accurate **by accident** (it counted all rows; all rows were caller
rows), and any future agent-side persistence would silently double it.

### `server.py` — persist the agent half (A4, byte-exact)

The existing `assistant` branch of `conversation_item_added` now writes the agent half through
the **same writer, same queue, same table, same enqueue-only contract** as the caller side:

```python
writer.record_turn(speaker="agent", text=text,
                   active_agent=persona, language=getattr(user_data, "language", None))
```

Attribution via `type(session.current_agent).__name__` guarded by `try/except` — `current_agent`
raises `RuntimeError` when the session has no agent (verified against livekit voice
`agent_session.py:580-585`). Nothing touches the voice path; a DB outage still degrades to a
dropped row, never a voice failure.

### `repositories.py` — P1-1 metric correction (A5, byte-exact)

`agent_activity` now adds `.where(Turn.speaker == "caller")`. Before P0-3 every row was a caller
row so the predicate was a no-op; the moment agent turns persist, omitting it would roughly
double the number under a column labelled **"Caller turns"**. The metric stays honest.

### Tests

- `apps/agent-worker/tests/conversation/test_writer_agent_turns.py` (5 tests) — agent-turn
  `record_turn` contract, queueing and speaker attribution.
- `apps/business-api/tests/test_agent_activity_speaker.py` (2 tests) — the **deliberate-red**
  pre-A5 test (agent rows must not inflate caller turn counts) + positive control. It failed
  before the A5 predicate and passed after — proving the fix is attributable, not a broken
  harness.

### `scripts/verify_p0_2.sh`

Check-1 exclusion extended with `':!docs/versions/version_84.md'` — the handoff changelog quotes
the removed variable in prose (same class as the existing `':!features_to_apply'` exclusion).

### Recorded deviations

- Applied on `version_84` (cookbook header said v83 — all five target blobs byte-identical
  across the two branches, user-approved).
- The three `record_turn` hits in pre-existing `test_writer.py` are baseline unit tests, not
  production third callers — treated as benign.
- Unused `# noqa: BLE001` directive dropped (BLE001 not in `pyproject.toml` select) so worker
  ruff is back to baseline 16; one isort blank line added in the business-api test file.

---

## Validation

- worker conversation suite: **8/8 PASS** (3 baseline + 5 new)
- business-api: **60/60 PASS** (58 baseline + 2 new; deliberate-red confirmed before A5)
- Full chain `test_committed.ps1 -Ref version_85`: **177/177 PASS**
  (business-api 60, agent-worker 90, notification 10, policy 17)
- `verify_p0_1.sh` 20/20 ; `verify_p0_2.sh` 9/9
- End-to-end probe from inside the agent-worker container: exactly `caller | 1 | P03Probe` and
  `agent | 2 | P03Probe` rows written, then cleaned up (`DELETE` 2 turns + 1 orphan session —
  never truncated, H-2 honoured); `turns` count back to 490
- ruff: worker src back to baseline **16**, main.py baseline preserved, both new test files
  clean
- Label gate (A5.3): overview "Turns" and agents "Caller turns" labels **left as-is** — A5
  already restricted `agent_activity` to caller-only turns, so "Caller turns" is now factually
  accurate; no frontend file changed
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`

---

## Out of scope (unchanged)

- Real-call verification (no live call since the container recreate; the in-container probe is
  the end-to-end proof instead)
- All items previously listed as out of scope in v79–v84.