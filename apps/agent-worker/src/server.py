"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, opens the durable conversation record, and starts
the worker. Conversation writes run off the voice path via ConversationWriter.
"""
from __future__ import annotations

import asyncio
import logging
import inspect
import os
import tracemalloc

import psutil

from agents.triage_agent import TriageAgent
from clients.context_client import get_context_client
from config import get_settings
from conversation.writer import ConversationWriter
from dotenv import load_dotenv
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
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from session import SessionUserData

from observability_kit import configure_tracer

load_dotenv()
logging.basicConfig(level=logging.INFO)
install_pii_masking()
logger = logging.getLogger("agent-worker")

async def _mem_probe() -> None:
    """Log Python allocation growth and Native Process RSS every 30s."""
    mem_logger = logging.getLogger("memprobe")
    mem_logger.setLevel(logging.WARNING)
    process = psutil.Process(os.getpid())
    while True:
        try:
            await asyncio.sleep(30)
            rss_mb = process.memory_info().rss / (1024 * 1024)
            current, peak = tracemalloc.get_traced_memory()
            top = tracemalloc.take_snapshot().statistics("lineno")[:5]
            mem_logger.warning(
                "SYSTEM_RSS_MB=%.1f | PYTHON_CUR_MB=%.1f | PYTHON_PEAK_MB=%.1f | TOP_ALLOCS=%s",
                rss_mb,
                current / 1e6,
                peak / 1e6,
                [f"{stat.traceback[0].filename.split('/')[-1]}:{stat.traceback[0].lineno}={stat.size // 1024}KB" for stat in top],
            )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            mem_logger.warning("memprobe failed: %s", exc)


settings = get_settings()


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


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    room_name = getattr(ctx.room, "name", None)
    logger.info("agent job received room=%s language=%s", room_name, language)

    tracemalloc.start(10)
    mem_probe_task = asyncio.create_task(_mem_probe())

    async def _stop_mem_probe() -> None:
        mem_probe_task.cancel()
        try:
            await mem_probe_task
        except asyncio.CancelledError:
            pass

    ctx.add_shutdown_callback(_stop_mem_probe)

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
