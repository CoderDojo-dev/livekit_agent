"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, opens the durable conversation record, and starts
the worker. Conversation writes run off the voice path via ConversationWriter.
"""
from __future__ import annotations

import logging
import inspect

from agents.triage_agent import TriageAgent
from clients.context_client import get_context_client
from config import get_settings
from conversation.writer import ConversationWriter
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext
from observability.log_masking import install_pii_masking
from observability.metrics_hook import attach_metrics
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from providers.turn_detection import register_inference_runners
from session import SessionUserData

from observability_kit import configure_tracer

load_dotenv()
logging.basicConfig(level=logging.INFO)
install_pii_masking()
logger = logging.getLogger("agent-worker")

settings = get_settings()

# --- Process-wide initialisation (once, never per-job) ---
configure_tracer("agent-worker")
register_inference_runners()


def _build_agent_server() -> AgentServer:
    """Create the AgentServer, naming it when the installed LiveKit SDK supports that option."""
    agent_name = settings.livekit_agent_name.strip()
    if agent_name:
        try:
            if "agent_name" in inspect.signature(AgentServer).parameters:
                logger.info("registering LiveKit worker agent_name=%s", agent_name)
                return AgentServer(agent_name=agent_name)
        except (TypeError, ValueError):
            pass
        logger.warning("LiveKit AgentServer has no agent_name constructor option; using auto-dispatch mode")
    return AgentServer()


server = _build_agent_server()


async def _prefetch_user_data(language: str) -> SessionUserData:
    """Build session state, pre-fetching the caller's Customer-360 snapshot when known."""
    user_data = SessionUserData(language=language)
    msisdn = settings.session_caller_msisdn
    if msisdn:
        snapshot = await get_context_client().get_snapshot(msisdn)
        if snapshot is not None:
            user_data.customer_context = snapshot
            logger.info("context prefetched: customer_id=%s vip=%s", snapshot.customer_id, snapshot.is_vip)
        else:
            logger.info("no context snapshot for the calling line")
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
        msisdn=settings.session_caller_msisdn or (customer.msisdn if customer else None),
        livekit_room=getattr(ctx.room, "name", None),
        recording_consent=user_data.recording_consent,
    )
    return writer


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    language = settings.session_language
    room_name = getattr(ctx.room, "name", None)
    logger.info("agent job received room=%s language=%s", room_name, language)

    session = build_agent_session(settings, language)
    user_data = await _prefetch_user_data(language)
    session.userdata = user_data

    writer = _open_conversation(ctx, user_data)

    async def _finish_conversation() -> None:
        history = user_data.sentiment_history or [0.0]
        writer.finish_session(
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()

    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(attach_metrics(session))

    @session.on("user_input_transcribed")
    def _on_user_transcribed(msg):
        text = getattr(msg, "text_content", "") or getattr(msg, "content", "")
        if text:
            logger.info("🎤 Caller: %s", text)

    @session.on("conversation_item_added")
    def _on_conversation_item(item):
        role = getattr(item, "role", "")
        text = getattr(item, "text", "") or getattr(item, "content", "")
        if role == "assistant" and text:
            logger.info("🤖 Agent: %s", text)

    @session.on("function_tools_executed")
    def _on_tools(fcs):
        names = [f.function_name for f in fcs] if fcs else []
        if names:
            logger.info("🛠️ Agent tools executed: %s", ", ".join(names))

    nc = build_noise_cancellation(settings.noise_cancellation)
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
    agents.cli.run_app(server)
