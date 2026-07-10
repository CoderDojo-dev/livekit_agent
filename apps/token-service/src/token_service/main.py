"""token-service (CDC web channel): mints a LiveKit JWT so a browser caller can join the room."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel, Field

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("token-service")

# Browser-facing signalling URL (ws:// dev, wss:// in staging/prod). Separate from service URLs.
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "telecom-agent").strip()
PILOT_MSISDN = os.getenv("PILOT_MSISDN", "").strip()
CALLER_MSISDN_ATTRIBUTE = "telecom.caller_msisdn"

app = FastAPI(title="token-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class TokenRequest(BaseModel):
    """A request for a room-join token."""

    room: str = "telecom-support"
    identity: str = "caller"
    name: str = "Caller"


class ClientEvent(BaseModel):
    """Browser-side call progress/error event, mirrored to service logs for live debugging."""

    event: str
    room: str | None = None
    identity: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TokenResponse(BaseModel):
    """A minted token plus the URL/room the client should connect to."""

    token: str
    url: str
    room: str
    agent_name: str | None = None


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/token", response_model=TokenResponse)
async def token(req: TokenRequest) -> TokenResponse:
    """Mint a 1-hour room-join token (reads LIVEKIT_API_KEY/SECRET from the environment)."""
    room_config = None
    if LIVEKIT_AGENT_NAME:
        room_config = api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name=LIVEKIT_AGENT_NAME)]
        )

    access_token = (
        api.AccessToken()
        .with_identity(req.identity)
        .with_name(req.name)
        .with_grants(
            api.VideoGrants(
                room_create=False,
                room_join=True,
                room=req.room,
                can_update_own_metadata=False,
            )
        )
        .with_attributes(
            {CALLER_MSISDN_ATTRIBUTE: PILOT_MSISDN}
            if PILOT_MSISDN
            else {}
        )
        .with_ttl(timedelta(minutes=15))
    )
    if room_config is not None:
        access_token = access_token.with_room_config(room_config)

    logger.info(
        "minted LiveKit token room=%s identity=%s url=%s agent_name=%s",
        req.room,
        req.identity,
        LIVEKIT_URL,
        LIVEKIT_AGENT_NAME or "<auto>",
    )
    return TokenResponse(
        token=access_token.to_jwt(),
        url=LIVEKIT_URL,
        room=req.room,
        agent_name=LIVEKIT_AGENT_NAME or None,
    )


@app.post("/client-events")
async def client_events(event: ClientEvent) -> dict[str, str]:
    """Mirror browser call progress to backend logs so debugging stays in the terminal."""
    logger.info(
        "client event=%s room=%s identity=%s details=%s",
        event.event,
        event.room,
        event.identity,
        event.details,
    )
    return {"status": "ok"}


def run() -> None:
    """Console-script entrypoint: `token-service` (see [project.scripts]). Serves on :8107."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8107)
