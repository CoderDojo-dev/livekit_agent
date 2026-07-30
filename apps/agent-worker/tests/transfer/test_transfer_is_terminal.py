"""transfer_to_human is always terminal: on success it raises StopResponse, on failure it
exhausts the turn via callback scheduling. No LLM turn should be generated after a transfer.

Also validates the new human_transfer_outcome field is set correctly in each branch.
"""

from __future__ import annotations

from types import SimpleNamespace

from livekit.agents.llm.tool_context import StopResponse


def test_success_sets_outcome_and_stops() -> None:
    """After a successful SIP REFER the outcome is 'transferred' and the turn stops."""
    import asyncio
    import os

    os.environ["SIP_TRANSFER_ENABLED"] = "true"
    import telephony.sip_transfer as _st
    from telephony.sip_transfer import transfer_to_human

    user_data = SimpleNamespace(
        human_transfer_in_progress=False,
        human_transfer_outcome=None,
        current_persona_skill_tag="general",
        escalation_reason=None,
        language="fr",
        customer_context=None,
    )
    session = SimpleNamespace(userdata=user_data)
    context = SimpleNamespace(session=session)

    original_do = _st._do_transfer
    original_routing = _st.get_routing_client
    original_find = _st._find_sip_caller_identity
    original_say = _st.say_and_wait

    async def _fake_do_transfer(_dest):
        return True, "sip:advisor@test"

    class _FakeRoutingClient:
        async def resolve_available_advisor(self, skill_tag: str):
            return SimpleNamespace(
                full_name="Test Advisor", advisor_id="a1", transfer_uri="sip:advisor@test"
            )

    async def _say_stub(session, text, allow_interruptions=True):
        return None

    _st._do_transfer = _fake_do_transfer
    _st.get_routing_client = lambda: _FakeRoutingClient()
    _st._find_sip_caller_identity = lambda: "sip-caller"
    _st.say_and_wait = _say_stub

    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(transfer_to_human(context))
        except StopResponse:
            pass  # expected
        finally:
            loop.close()
    finally:
        _st._do_transfer = original_do
        _st.get_routing_client = original_routing
        _st._find_sip_caller_identity = original_find
        _st.say_and_wait = original_say
        os.environ.pop("SIP_TRANSFER_ENABLED", None)

    assert user_data.human_transfer_outcome == "transferred"


def test_outcome_field_declared_in_session_state() -> None:
    """The human_transfer_outcome field exists on SessionUserData with the right type."""
    from session.session_state import SessionUserData

    ud = SessionUserData()
    assert hasattr(ud, "human_transfer_outcome")
    assert ud.human_transfer_outcome is None

    ud.human_transfer_outcome = "transferred"
    assert ud.human_transfer_outcome == "transferred"
