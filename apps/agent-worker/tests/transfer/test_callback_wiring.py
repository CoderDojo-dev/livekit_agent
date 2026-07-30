"""The callback chain must pass reason= and customer_context= to CallbackScheduleTask."""
import asyncio
import types
from unittest.mock import AsyncMock, MagicMock, patch

from tools.escalation_policy import EscalationPolicy


class _Session:
    def __init__(self):
        self.userdata = types.SimpleNamespace(
            language="fr", clarification_attempts=0, identity_attempts=1,
            should_offer_escalation=False, conversation_writer=None,
            current_persona_skill_tag="general", human_transfer_announced=False,
            customer_context=None,
        )
        self.current_agent = MagicMock()


class _Ctx:
    def __init__(self):
        self.session = _Session()


@patch("telephony.sip_transfer.CallbackScheduleTask", new_callable=AsyncMock)
@patch("telephony.sip_transfer._notify_on_call_advisors", new_callable=AsyncMock)
def test_offer_callback_passes_reason_and_customer_context(MockNotify, MockTask) -> None:
    from telephony.sip_transfer import _offer_callback

    MockTask.return_value = True
    MockNotify.return_value = 1
    ctx = _Ctx()
    result = asyncio.run(_offer_callback(ctx, reason="no_advisor_available"))
    assert result["outcome"] in ("callback_scheduled", "callback_declined")
    MockTask.assert_called_once()
    _, kwargs = MockTask.call_args
    assert "reason" in kwargs
    assert kwargs["reason"] == "no_advisor_available"
    assert "customer_context" in kwargs


@patch("telephony.sip_transfer.CallbackScheduleTask", new_callable=AsyncMock)
@patch("telephony.sip_transfer._notify_on_call_advisors", new_callable=AsyncMock)
def test_offer_callback_does_not_pass_tts(MockNotify, MockTask) -> None:
    from telephony.sip_transfer import _offer_callback

    MockTask.return_value = True
    MockNotify.return_value = 1
    ctx = _Ctx()
    asyncio.run(_offer_callback(ctx, reason="transfer_failed"))
    _, kwargs = MockTask.call_args
    assert "tts" not in kwargs
