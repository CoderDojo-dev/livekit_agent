"""v79: a handoff must carry a new caller intent, and a call has a handoff budget."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from livekit.agents.llm.tool_context import StopResponse
from tools.voice_flow import MAX_HANDOFFS_PER_CALL, handoff_with_message


class _Speech:
    def interrupt(self, force: bool = False) -> None:
        return None

    def __await__(self):
        async def _done() -> None:
            return None

        return _done().__await__()


class _Session:
    def __init__(self, userdata) -> None:
        self.userdata = userdata
        self.said: list[str] = []
        self.current_agent = None

    def say(self, text: str, allow_interruptions: bool = True) -> _Speech:
        self.said.append(text)
        return _Speech()


class _Ctx:
    def __init__(self, session: _Session) -> None:
        self.session = session


class _Target:
    pass


def _context() -> _Ctx:
    return _Ctx(_Session(SimpleNamespace(caller_turn_index=1)))


@pytest.mark.asyncio
async def test_first_handoff_is_allowed() -> None:
    ctx = _context()
    target = _Target()

    assert await handoff_with_message(ctx, target, "transition") is target
    assert ctx.session.userdata.handoff_count == 1
    assert ctx.session.userdata.last_handoff_turn == 1


@pytest.mark.asyncio
async def test_second_handoff_on_the_same_caller_turn_is_refused() -> None:
    ctx = _context()
    await handoff_with_message(ctx, _Target(), "transition")

    with pytest.raises(StopResponse):
        await handoff_with_message(ctx, _Target(), "transition", language="fr")

    assert ctx.session.userdata.handoff_count == 1
    assert "Je dois clôturer cet appel" in ctx.session.said[-1]


@pytest.mark.asyncio
async def test_a_new_caller_turn_unlocks_the_next_handoff() -> None:
    ctx = _context()
    await handoff_with_message(ctx, _Target(), "transition")

    ctx.session.userdata.caller_turn_index += 1
    target = _Target()

    assert await handoff_with_message(ctx, target, "transition") is target
    assert ctx.session.userdata.handoff_count == 2


@pytest.mark.asyncio
async def test_handoff_budget_is_capped_per_call() -> None:
    ctx = _context()
    for _ in range(MAX_HANDOFFS_PER_CALL):
        ctx.session.userdata.caller_turn_index += 1
        await handoff_with_message(ctx, _Target(), "transition")

    ctx.session.userdata.caller_turn_index += 1
    with pytest.raises(StopResponse):
        await handoff_with_message(ctx, _Target(), "transition")


@pytest.mark.asyncio
async def test_manager_escalation_is_never_refused() -> None:
    ctx = _context()
    await handoff_with_message(ctx, _Target(), "transition")

    manager = _Target()
    assert (
        await handoff_with_message(ctx, manager, "transition", loop_guard=False)
        is manager
    )
