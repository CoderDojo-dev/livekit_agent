"""SIP transfer / human escalation (cookbook section 15; Blueprint section 5.12 / ADR 5.4).

Every branch of this flow produces honest speech - the caller is never left in silence, and is
never told a transfer happened when it did not:

  advisor claimed + transfer succeeds -> the call moves to the advisor (cold transfer)
  advisor claimed + transfer fails    -> advisor released, caller told plainly, callback offered
  no advisor available                -> caller told plainly, callback offered
  callback scheduled                  -> the on-call advisor is notified WITH the dossier, so the
                                         promise of a call back is backed by a real human

TransferSIPParticipant performs a SIP REFER on the caller's own SIP participant, so it needs the
identity of the SIP participant in the room (assigned at dispatch, not the phone number) - found
by filtering remote participants on ParticipantKind.SIP. Passing anything else fails with an
identity mismatch. It is a cold transfer: the caller's LiveKit session ends once it completes.
"""
from __future__ import annotations

import logging
import os
from contextlib import suppress

from clients.routing_client import AdvisorDestination, get_routing_client
from livekit.agents import RunContext, function_tool, get_job_context
from livekit.agents.llm.tool_context import StopResponse
from tasks.callback_schedule_task import CallbackScheduleTask
from tools.voice_flow import say_and_wait

logger = logging.getLogger(__name__)

_TRANSFER_MESSAGES = {
    "fr": "Je vous mets en relation avec un conseiller. Veuillez patienter.",
    "ar": "سأقوم الآن بتحويلك إلى أحد المستشارين. يرجى الانتظار.",
    "en": "I am connecting you with an advisor. Please hold.",
}

_NO_ADVISOR_MESSAGES = {
    "fr": "Aucun conseiller n'est disponible pour le moment.",
    "ar": "لا يوجد مستشار متاح في الوقت الحالي.",
    "en": "No advisor is available right now.",
}


def _language(user_data) -> str:
    """2-letter language code, tolerating an enum or a locale like "fr-FR" (as elsewhere)."""
    raw = getattr(user_data, "language", "fr")
    value = getattr(raw, "value", raw)
    code = str(value or "fr").lower().strip()[:2]
    return code if code in _TRANSFER_MESSAGES else "fr"


def _find_sip_caller_identity() -> str | None:
    """Identity of the caller's SIP participant in the room, or None outside telephony.

    Required by TransferSIPParticipant: the REFER is issued on the caller's SIP leg. In a console
    or web session there is no SIP participant, so a transfer is genuinely impossible and the
    caller must be offered a callback instead.
    """
    try:
        from livekit import rtc

        job = get_job_context()
        for participant in job.room.remote_participants.values():
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                return participant.identity
    except Exception as exc:
        logger.warning("could not inspect room participants: %s", exc)
    return None


async def _notify_on_call_advisors(context: RunContext, dossier: dict) -> int:
    """Send the escalation dossier to every on-call advisor. Returns how many were reached."""
    from clients.notification_client import get_notification_client

    advisors = await get_routing_client().on_call_advisors()
    if not advisors:
        logger.error("callback scheduled but NO on-call advisor is configured to receive it")
        return 0

    notified = 0
    client = get_notification_client()
    for advisor in advisors:
        for channel, handle in (("whatsapp", advisor.get("phone_e164")),
                                ("email", advisor.get("email"))):
            if not handle:
                continue
            sent = await client.notify_advisor(
                channel=channel, to=handle, template="advisor_callback",
                language=advisor.get("language") or "fr", params=dossier,
            )
            if sent:
                notified += 1
                break
    return notified


async def _offer_callback(context: RunContext, reason: str) -> dict:
    """Schedule a callback and make sure a real human is told about it."""
    user_data = context.session.userdata
    scheduled = await CallbackScheduleTask(reason=reason, customer_context=getattr(user_data, "customer_context", None))
    if not scheduled:
        return {
            "outcome": "callback_declined",
            "reason": reason,
            "message": "No advisor is available and no callback was scheduled; say plainly "
                       "that they can call back at any time.",
        }

    customer = getattr(user_data, "customer_context", None)
    dossier = {
        "customer_id": getattr(customer, "customer_id", "") or "",
        "msisdn": getattr(customer, "msisdn", "") or "",
        "full_name": getattr(customer, "full_name", "") or "",
        "reason": reason,
        "skill_tag": getattr(user_data, "current_persona_skill_tag", "general"),
        "language": _language(user_data),
    }
    notified = await _notify_on_call_advisors(context, dossier)
    return {
        "outcome": "callback_scheduled",
        "reason": reason,
        "advisors_notified": notified,
        "message": (
            "A callback is scheduled and an advisor has been notified."
            if notified
            else "A callback is recorded but no advisor could be notified; do not promise a "
                 "specific time, and say the request has been registered."
        ),
    }


async def _do_transfer(destination: AdvisorDestination) -> tuple[bool, str]:
    """Issue the SIP REFER. Returns (succeeded, detail)."""
    caller_identity = _find_sip_caller_identity()
    if caller_identity is None:
        return False, "no SIP participant in the room (not a telephony call)"

    try:
        from livekit import api

        job = get_job_context()
        await job.api.sip.transfer_sip_participant(
            api.TransferSIPParticipantRequest(
                room_name=job.room.name,
                participant_identity=caller_identity,
                transfer_to=destination.transfer_uri,
                play_dialtone=True,
            )
        )
        return True, destination.transfer_uri
    except Exception as exc:
        return False, str(exc)


@function_tool()
async def transfer_to_human(context: RunContext) -> dict:
    """Transfer the caller to a live human advisor; if none is free, schedule a callback."""
    user_data = context.session.userdata

    if getattr(user_data, "human_transfer_in_progress", False):
        return {
            "outcome": "transfer_already_in_progress",
            "message": "A transfer is already under way: briefly ask the caller to hold, "
                       "and say nothing else.",
        }

    if os.getenv("SIP_TRANSFER_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logger.info("SIP transfer disabled; offering a callback directly")
        user_data.escalation_reason = "sip_unavailable"
        user_data.human_transfer_outcome = "callback_only"
        return await _offer_callback(context, reason="sip_unavailable")

    user_data.human_transfer_in_progress = True
    skill_tag = getattr(user_data, "current_persona_skill_tag", "general")
    language = _language(user_data)

    try:
        with suppress(Exception):
            context.disallow_interruptions()

        destination = await get_routing_client().resolve_available_advisor(skill_tag)
        if destination is None and skill_tag != "general":
            # Fix 2 now sends a real skill tag; never regress a caller into a callback
            # just because no specialist advisor is free.
            logger.info("no %r advisor free; falling back to a generalist", skill_tag)
            destination = await get_routing_client().resolve_available_advisor("general")

        if destination is None:
            await say_and_wait(
                context.session,
                _NO_ADVISOR_MESSAGES.get(language, _NO_ADVISOR_MESSAGES["fr"]),
                allow_interruptions=False,
            )
            user_data.escalation_reason = "no_advisor_available"
            user_data.human_transfer_outcome = "no_advisor"
            return await _offer_callback(context, reason="no_advisor_available")

        if not getattr(user_data, "human_transfer_announced", False):
            user_data.human_transfer_announced = True
            await say_and_wait(
                context.session,
                _TRANSFER_MESSAGES.get(language, _TRANSFER_MESSAGES["fr"]),
                allow_interruptions=False,
            )

        succeeded, detail = await _do_transfer(destination)
        if succeeded:
            logger.info(
                "SIP transfer completed (advisor=%s skill=%s)", destination.full_name, skill_tag
            )
            user_data.human_transfer_outcome = "transferred"
            # The caller's leg is gone: stop the turn so no LLM/TTS output is billed
            # for an empty room, and no advisor name is read aloud.
            raise StopResponse()

        logger.warning("SIP transfer failed (%s); releasing advisor and offering a callback", detail)
        await get_routing_client().release_advisor(destination.advisor_id)
        await say_and_wait(
            context.session,
            _NO_ADVISOR_MESSAGES.get(language, _NO_ADVISOR_MESSAGES["fr"]),
            allow_interruptions=False,
        )
        user_data.escalation_reason = "transfer_failed"
        user_data.human_transfer_outcome = "transfer_failed"
        return await _offer_callback(context, reason="transfer_failed")
    finally:
        user_data.human_transfer_in_progress = False