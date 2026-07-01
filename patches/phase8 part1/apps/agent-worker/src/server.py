"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, attaches sentiment, and starts the worker.
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext

from agents.triage_agent import TriageAgent
from clients.context_client import get_context_client
from config import get_settings
from observability.log_masking import install_pii_masking
from observability.metrics_hook import attach_metrics
from observability_kit import configure_tracer
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from sentiment.sentiment_hook import attach_sentiment
from session import SessionUserData

load_dotenv()
logging.basicConfig(level=logging.INFO)
install_pii_masking()  # scrub PII from every log record (Blueprint section 14)
logger = logging.getLogger("agent-worker")

settings = get_settings()
server = AgentServer()


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


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    logger.info("starting Triage session language=%s", language)

    session = build_agent_session(settings, language)
    session.userdata = await _prefetch_user_data(language)

    shutdown_cb = attach_metrics(session)
    ctx.add_shutdown_callback(shutdown_cb)
    attach_sentiment(session)  # post-turn frustration signal -> ESC_FRUSTRATION rule

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
        except Exception as exc:  # noqa: BLE001 - isolate a fast-moving room-options API
            logger.warning("noise-cancellation room options unavailable (%s); plain start", exc)
            await session.start(agent=TriageAgent(language=language), room=ctx.room)


if __name__ == "__main__":
    agents.cli.run_app(server)