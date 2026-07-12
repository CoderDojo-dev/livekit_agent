"""SIP transfer / human escalation (cookbook section 15; Blueprint section 5.12 / ADR 5.4).

Resolves the advisor destination dynamically (never a hardcoded trunk). If none is free, or if
SIP transfer is unavailable (e.g. console/dev with no trunk), it falls back to scheduling a
callback. [VERIFY] the SIP transfer call requires SIP REFER on the trunk; it is a cold transfer
that ends the current session, so it runs only in the telephony path and is guarded defensively.
"""
from __future__ import annotations

import logging
from contextlib import suppress

from clients.routing_client import get_routing_client
from livekit.agents import RunContext, function_tool, get_job_context
from tasks.callback_schedule_task import CallbackScheduleTask
from tools.voice_flow import say_and_wait

logger = logging.getLogger(__name__)

_TRANSFER_MESSAGES = {
    "fr": "Je vous mets en relation avec un conseiller. Veuillez patienter.",
    "ar": "سأقوم الآن بتحويلك إلى أحد المستشارين. يرجى الانتظار.",
    "en": "I am connecting you with an advisor. Please hold.",
}


async def _offer_callback(context: RunContext) -> dict:
    scheduled = await CallbackScheduleTask()
    return {"outcome": "callback_scheduled" if scheduled else "callback_declined"}


@function_tool()
async def transfer_to_human(context: RunContext) -> dict:
    """Transfer the caller to a live human advisor; if none is free, schedule a callback."""
    user_data = context.session.userdata

    if getattr(user_data, "human_transfer_in_progress", False):
        return {"outcome": "transfer_already_in_progress"}

    user_data.human_transfer_in_progress = True
    skill_tag = getattr(user_data, "current_persona_skill_tag", "general")

    try:
        with suppress(Exception):
            context.disallow_interruptions()

        # One component owns this announcement, and it can only happen once.
        if not getattr(user_data, "human_transfer_announced", False):
            user_data.human_transfer_announced = True
            language = getattr(user_data, "language", "fr")
            await say_and_wait(
                context.session,
                _TRANSFER_MESSAGES.get(language, _TRANSFER_MESSAGES["fr"]),
                allow_interruptions=False,
            )

        destination = await get_routing_client().resolve_available_advisor(skill_tag)
        if destination is None:
            return await _offer_callback(context)

        try:
            from livekit import api

            job = get_job_context()
            await job.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job.room.name,
                    participant_identity=destination.participant_identity,
                    transfer_to=destination.sip_uri,
                )
            )
            return {"outcome": "transferred", "destination": destination.sip_uri}
        except Exception as exc:
            logger.warning("SIP transfer unavailable (%s); offering a callback", exc)
            return await _offer_callback(context)
    finally:
        user_data.human_transfer_in_progress = False
