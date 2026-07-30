"""Une escalade sans consentement doit etre refusee, sauf abus/fraude."""
import asyncio
import types
from unittest.mock import MagicMock

from tools import escalation_tools


class _Session:
    def __init__(self):
        self.userdata = types.SimpleNamespace(
            language="fr", clarification_attempts=0, identity_attempts=1,
            should_offer_escalation=False, conversation_writer=None,
            current_persona_skill_tag="general", human_transfer_announced=False,
            offer_count=0, user_refused_manager=False, can_hardfail=True,
        )
        self.current_agent = MagicMock()
        self.current_agent.chat_ctx = MagicMock()


class _Ctx:
    def __init__(self):
        self.session = _Session()


class _FakeManager:
    def __init__(self, chat_ctx=None, language=None):
        self.chat_ctx = chat_ctx
        self.language = language


def _call(**kwargs):
    # Patch escalation_tools dependencies that need a real LiveKit session
    original_manager = escalation_tools.ManagerAgent
    escalation_tools.ManagerAgent = _FakeManager

    async def _fake_handoff(_ctx, _agent, _msg):
        return _agent

    original_handoff = escalation_tools.handoff_with_message
    escalation_tools.handoff_with_message = _fake_handoff

    tool = escalation_tools.escalate_to_manager
    fn = getattr(tool, "__wrapped__", None) or getattr(tool, "fn", tool)
    try:
        return asyncio.run(fn(_Ctx(), **kwargs))
    finally:
        escalation_tools.ManagerAgent = original_manager
        escalation_tools.handoff_with_message = original_handoff


def test_without_consent_returns_an_instruction_not_an_agent():
    result = _call(reason="cannot_help", caller_agreed=False)
    assert isinstance(result, str)
    assert "manager" in result.lower()


def test_identity_failure_alone_does_not_escalate():
    result = _call(reason="identity_fail", caller_agreed=False)
    assert isinstance(result, str)


def test_abuse_escalates_without_consent():
    result = _call(reason="abuse", caller_agreed=False)
    assert not isinstance(result, str)
