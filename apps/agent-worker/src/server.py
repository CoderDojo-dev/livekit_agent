"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, opens the durable conversation record, and starts
the worker. Conversation writes run off the voice path via ConversationWriter.
"""
from __future__ import annotations

import logging

from agents.triage_agent import TriageAgent
from clients import aclose_all_clients
from clients.context_client import get_context_client
from clients.nms_client import get_nms_client
from config import get_settings
from conversation.writer import ConversationWriter
from dotenv import load_dotenv
from frontend_events import FrontendEventPublisher
from livekit import agents
from livekit.agents import (
    AgentServer,
    ConversationItemAddedEvent,
    FunctionToolsExecutedEvent,
    JobContext,
)
from livekit.agents.llm import ChatMessage
from observability.log_masking import install_pii_masking
from observability.metrics_hook import attach_metrics
from providers._resilience import monitor_room_resilience
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from session import SessionUserData

from observability_kit import configure_tracer

load_dotenv()
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(level=logging.INFO)
install_pii_masking()
from providers.tts_audit import install_tts_audit

install_tts_audit()

logger = logging.getLogger("agent-worker")

settings = get_settings()
CALLER_MSISDN_ATTRIBUTE = "telecom.caller_msisdn"


server = AgentServer(
    num_idle_processes=1,
    job_memory_warn_mb=768,
)


async def _prefetch_user_data(
    language: str,
    participant,
) -> SessionUserData:
    """Load Customer-360 from trusted signed participant attributes."""
    user_data = SessionUserData(language=language)
    msisdn = participant.attributes.get(
        CALLER_MSISDN_ATTRIBUTE,
        "",
    ).strip()

    if not msisdn:
        logger.info("no trusted caller MSISDN attribute")
        return user_data

    snapshot = await get_context_client().get_snapshot(msisdn)
    if snapshot is not None:
        user_data.customer_context = snapshot
        user_data.language = snapshot.preferred_language
        logger.info(
            "context prefetched: customer_id=%s vip=%s",
            snapshot.customer_id,
            snapshot.is_vip,
        )
    else:
        logger.info("no context snapshot for trusted calling line")
    return user_data


def _open_conversation(ctx: JobContext, user_data: SessionUserData) -> ConversationWriter:
    """Start the conversation writer and open the call record (off the voice path)."""
    writer = ConversationWriter()
    writer.start()
    customer = user_data.customer_context
    user_data.conversation_writer = writer
    user_data.session_db_id = writer.start_session(
        customer_id=customer.customer_id if customer else None,
        subscription_id=getattr(customer, "subscription_id", None) if customer else None,
        msisdn=customer.msisdn if customer else None,
        livekit_room=getattr(ctx.room, "name", None),
        recording_consent=user_data.recording_consent,
    )
    return writer


def _derive_disposition(user_data: SessionUserData) -> str:
    """How this call ended, in conversation.call_sessions.final_disposition's own vocabulary.

    P1-2 - the column, its CHECK constraint and the writer parameter all existed, but the single
    shutdown call site never passed a value, so every row was NULL and every disposition-derived
    read (kpis, analytics_trend, telemetry_timeline, session_detail, the /sessions filter)
    reported zero or "unknown". This decides nothing new: it reads state the session already
    maintains and maps it onto the four values the CHECK constraint permits.

    Escalation wins over a graceful close: a completed SIP transfer raises StopResponse and the
    caller's leg is gone, so end_conversation cannot also have run. "dropped" is the fallback
    rather than "resolved" - a call that ended without the agent closing it did not demonstrably
    resolve anything, and guessing otherwise would inflate the very KPI this makes truthful.
    """
    if user_data.human_transfer_outcome or user_data.escalation_reason:
        return "escalated"
    if user_data.conversation_ending:
        return "resolved"
    if user_data.caller_turn_index == 0:
        return "abandoned"
    return "dropped"


@server.rtc_session(agent_name=settings.livekit_agent_name.strip())
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    room_name = getattr(ctx.room, "name", None)
    participant = await ctx.wait_for_participant()
    logger.info("agent job received room=%s language=%s", room_name, language)

    user_data = await _prefetch_user_data(language, participant)
    language = user_data.language
    keyterms = await get_nms_client().get_geo_keyterms(language)
    session = build_agent_session(settings, language, keyterms)
    session.userdata = user_data

    frontend_events = FrontendEventPublisher(ctx.room)
    writer = _open_conversation(ctx, user_data)

    async def _finish_conversation() -> None:
        history = user_data.sentiment_history or [0.0]
        writer.finish_session(
            disposition=_derive_disposition(user_data),
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()

    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(frontend_events.aclose)
    ctx.add_shutdown_callback(attach_metrics(session, writer))
    ctx.add_shutdown_callback(aclose_all_clients)  # release httpx pools (patch #10)

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
            # P0-3 - persist the agent half of the transcript. The text is already in
            # hand here; before this it was logged and discarded, so every stored
            # conversation was a monologue. Same writer, same queue, same table and
            # the same enqueue-only contract as the caller side: nothing here touches
            # the voice path, and a DB outage still degrades to a dropped row.
            try:
                persona = type(session.current_agent).__name__
            except Exception:  # no active agent yet; attribution is optional
                persona = None
            writer.record_turn(
                speaker="agent",
                text=text,
                active_agent=persona,
                language=getattr(user_data, "language", None),
            )

    @session.on("function_tools_executed")
    def _on_function_tools_executed(event: FunctionToolsExecutedEvent):
        names = [fc.name for fc in event.function_calls] if event.function_calls else []
        if names:
            logger.info("🛠️✅ Tools executed: %s", ", ".join(names))
            frontend_events.publish_tool_batch(event)

    nc = build_noise_cancellation(settings.noise_cancellation)
    monitor_room_resilience(ctx.room, session, user_data)
    if nc is None:
        await session.start(agent=TriageAgent(language=language), room=ctx.room)
    else:
        try:
            from livekit.agents import room_io

            await session.start(
                agent=TriageAgent(language=language),
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    audio_input=room_io.AudioInputOptions(noise_cancellation=nc),
                ),
            )
        except Exception as exc:
            logger.warning("noise-cancellation room options unavailable (%s); plain start", exc)
            await session.start(agent=TriageAgent(language=language), room=ctx.room)
    logger.info("Triage session started room=%s", room_name)


if __name__ == "__main__":
    root_logger.handlers.clear()
    agents.cli.run_app(server)
