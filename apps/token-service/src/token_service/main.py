"""token-service (CDC web channel): mints a LiveKit JWT so a browser caller can join the room."""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
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

# A caller-supplied MSISDN decides which subscriber the agent resolves, so it is
# only trusted from a caller that proves it is one of our own servers. The
# customer portal's voice.server.ts holds this key already (server-side only);
# apps/client-widget sends neither key nor MSISDN and is unaffected.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()
INTERNAL_KEY_HEADER = "x-internal-api-key"

app = FastAPI(title="token-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", INTERNAL_KEY_HEADER],
)


class TokenRequest(BaseModel):
    """A request for a room-join token."""

    room: str = "telecom-support"
    identity: str = "caller"
    name: str = "Caller"
    caller_msisdn: str | None = None


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
async def token(req: TokenRequest, request: Request) -> TokenResponse:
    """Mint a 15-minute room-join token (reads LIVEKIT_API_KEY/SECRET from the environment).

    caller_msisdn is honoured only for trusted internal callers: it selects the
    subscriber the agent will serve, so an anonymous browser must never choose
    it. Untrusted callers fall back to PILOT_MSISDN, which is the pre-existing
    behaviour for every current client.
    """
    room_config = None
    if LIVEKIT_AGENT_NAME:
        room_config = api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name=LIVEKIT_AGENT_NAME)]
        )

    trusted = bool(INTERNAL_API_KEY) and (
        request.headers.get(INTERNAL_KEY_HEADER, "") == INTERNAL_API_KEY
    )
    if req.caller_msisdn and not trusted:
        logger.warning(
            "ignored caller_msisdn from untrusted caller identity=%s room=%s",
            req.identity,
            req.room,
        )
    caller_msisdn = (req.caller_msisdn if trusted else None) or PILOT_MSISDN
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
            {CALLER_MSISDN_ATTRIBUTE: caller_msisdn}
            if caller_msisdn
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
