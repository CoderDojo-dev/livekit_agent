"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks and starts the
worker. No business logic, no provider config detail, no tool implementation lives here.
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext

from agents.triage_agent import TriageAgent
from config import get_settings
from observability.metrics_hook import attach_metrics
from observability_kit import configure_tracer
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from session import SessionUserData

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-worker")

settings = get_settings()
server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    logger.info("starting Triage session language=%s", language)

    session = build_agent_session(settings, language)
    session.userdata = SessionUserData(language=language)

    shutdown_cb = attach_metrics(session)
    ctx.add_shutdown_callback(shutdown_cb)

    nc = build_noise_cancellation(settings.noise_cancellation)
    if nc is None:
        await session.start(agent=TriageAgent(language=language), room=ctx.room)
    else:
        # [VERIFY] room_io options API; falls back to a plain start if the signature differs.
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