from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from livekit.agents.llm.tool_context import StopResponse
from tools import clarification_tools, escalation_tools, routing_tools
from tools.voice_flow import say_and_wait


class FakeSpeech:
    def __init__(self, *, hang: bool = False) -> None:
        self.hang = hang
        self.interrupted = False
        self._released = asyncio.Event()

    async def _wait(self):
        if self.hang:
            await self._released.wait()
        return self

    def __await__(self):
        return self._wait().__await__()

    def interrupt(self, force: bool = False) -> None:
        self.interrupted = True
        self._released.set()


class FakeSession:
    def __init__(self, userdata=None, *, hang: bool = False) -> None:
        self.userdata = userdata or SimpleNamespace()
        self.current_agent = SimpleNamespace(chat_ctx=object())
        self.hang = hang
        self.say_calls: list[tuple[str, bool]] = []
        self.speeches: list[FakeSpeech] = []

    def say(self, text: str, *, allow_interruptions: bool):
        self.say_calls.append((text, allow_interruptions))
        speech = FakeSpeech(hang=self.hang)
        self.speeches.append(speech)
        return speech


def make_userdata(**overrides):
    values = {
        "clarification_attempts": 0,
        "identity_attempts": 0,
        "identity_verified": False,
        "should_offer_escalation": False,
        "consecutive_negative_turns": 0,
        "customer_context": None,
        "conversation_writer": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_context(userdata=None, *, hang: bool = False):
    session = FakeSession(userdata or make_userdata(), hang=hang)
    return SimpleNamespace(session=session), session


def test_say_and_wait_completes():
    async def run():
        session = FakeSession()
        speech = await say_and_wait(
            session,
            "hello",
            allow_interruptions=True,
            timeout_s=0.1,
        )
        assert speech is session.speeches[0]
        assert session.say_calls == [("hello", True)]
        assert not speech.interrupted

    asyncio.run(run())


def test_say_and_wait_times_out_and_interrupts():
    async def run():
        session = FakeSession(hang=True)
        with pytest.raises(TimeoutError):
            await say_and_wait(
                session,
                "hello",
                allow_interruptions=True,
                timeout_s=0.01,
            )
        assert session.speeches[0].interrupted

    asyncio.run(run())


def test_say_and_wait_rejects_empty_text():
    async def run():
        session = FakeSession()
        with pytest.raises(ValueError):
            await say_and_wait(
                session,
                "   ",
                allow_interruptions=True,
            )
        assert session.say_calls == []

    asyncio.run(run())


def test_first_clarification_speaks_and_stops_response():
    async def run():
        context, session = make_context()
        with pytest.raises(StopResponse):
            await clarification_tools.request_clarification(
                context,
                "Pouvez-vous préciser votre problème ?",
            )

        assert context.session.userdata.clarification_attempts == 1
        assert session.say_calls == [
            ("Pouvez-vous préciser votre problème ?", True)
        ]

    asyncio.run(run())


def test_empty_clarification_uses_safe_fallback():
    async def run():
        context, session = make_context()
        with pytest.raises(StopResponse):
            await clarification_tools.request_clarification(context, " ")

        assert session.say_calls
        assert session.say_calls[0][0]
        assert session.say_calls[0][1] is True

    asyncio.run(run())


def test_second_clarification_hands_off(monkeypatch):
    async def fake_escalate(context):
        return "manager-agent"

    monkeypatch.setattr(
        clarification_tools,
        "escalate_to_manager",
        fake_escalate,
    )

    async def run():
        userdata = make_userdata(clarification_attempts=1)
        context, session = make_context(userdata)

        result = await clarification_tools.request_clarification(
            context,
            "Encore une précision ?",
        )

        assert result == "manager-agent"
        assert userdata.clarification_attempts == 2
        assert session.say_calls == []

    asyncio.run(run())


@pytest.mark.parametrize(
    ("function_name", "agent_attribute", "expected_type"),
    [
        ("route_to_account_services", "AccountServicesAgent", "account"),
        ("route_to_billing", "BillingAgent", "billing"),
        ("route_to_technical", "TechnicalAgent", "technical"),
    ],
)
def test_specialist_handoffs_preserve_context(
    monkeypatch,
    function_name,
    agent_attribute,
    expected_type,
):
    class FakeAgent:
        def __init__(self, chat_ctx=None):
            self.chat_ctx = chat_ctx
            self.kind = expected_type

    monkeypatch.setattr(routing_tools, agent_attribute, FakeAgent)

    async def run():
        context, session = make_context()
        original_chat_ctx = session.current_agent.chat_ctx

        result = await getattr(routing_tools, function_name)(context)

        assert result.kind == expected_type
        assert result.chat_ctx is original_chat_ctx
        assert session.say_calls == []

    asyncio.run(run())


class FakeWriter:
    def __init__(self):
        self.calls = []

    def record_escalation(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.parametrize(
    ("overrides", "expected_trigger"),
    [
        ({"should_offer_escalation": True}, "frustration"),
        ({"clarification_attempts": 2}, "clarify_fail"),
        ({"identity_attempts": 3}, "identity_fail"),
        ({}, "hard_failure"),
    ],
)
def test_manager_escalation_paths(
    monkeypatch,
    overrides,
    expected_trigger,
):
    class FakeManager:
        def __init__(self, chat_ctx=None):
            self.chat_ctx = chat_ctx

    monkeypatch.setattr(escalation_tools, "ManagerAgent", FakeManager)

    async def run():
        writer = FakeWriter()
        userdata = make_userdata(
            conversation_writer=writer,
            **overrides,
        )
        context, session = make_context(userdata)
        original_chat_ctx = session.current_agent.chat_ctx

        result = await escalation_tools.escalate_to_manager(context)

        assert isinstance(result, FakeManager)
        assert result.chat_ctx is original_chat_ctx
        assert session.say_calls == []
        assert writer.calls[0]["trigger"] == expected_trigger

    asyncio.run(run())


def test_no_tool_calls_session_interrupt_directly():
    root = Path(__file__).parents[2]
    tools_dir = root / "src" / "tools"

    offenders = []
    for path in tools_dir.glob("*.py"):
        if "context.session.interrupt(" in path.read_text():
            offenders.append(path.name)

    assert offenders == []


def test_all_interactive_agent_tasks_remain_bounded_and_idempotent():
    root = Path(__file__).parents[2]
    tasks_dir = root / "src" / "tasks"

    interactive_tasks = [
        "consent_task.py",
        "identity_verification_task.py",
        "payment_confirm_task.py",
        "callback_schedule_task.py",
        "sim_replacement_task_group.py",
    ]

    for filename in interactive_tasks:
        text = (tasks_dir / filename).read_text(encoding="utf-8")
        assert "function_tool" in text, filename
        assert "async def on_enter" in text, filename
        assert "self.complete(" in text, filename
