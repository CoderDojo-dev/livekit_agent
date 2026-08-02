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
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()

    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(frontend_events.aclose)
    ctx.add_shutdown_callback(attach_metrics(session))
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
