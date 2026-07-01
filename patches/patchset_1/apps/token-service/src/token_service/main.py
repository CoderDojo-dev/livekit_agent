"""token-service (CDC web channel): mints a LiveKit JWT so a browser caller can join the room.

The worker registers with NO agent_name, so LiveKit AUTOMATICALLY dispatches it to every new
room - a plain room_join token is enough for the caller to reach the agent. For a named agent,
add a RoomConfiguration with RoomAgentDispatch (see the commented block below).
"""
from __future__ import annotations

import os
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel

load_dotenv()

# Browser-facing signalling URL (ws:// dev, wss:// in staging/prod). Separate from service URLs.
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

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


class TokenResponse(BaseModel):
    """A minted token plus the URL/room the client should connect to."""

    token: str
    url: str
    room: str


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/token", response_model=TokenResponse)
async def token(req: TokenRequest) -> TokenResponse:
    """Mint a 1-hour room-join token (reads LIVEKIT_API_KEY/SECRET from the environment)."""
    access_token = (
        api.AccessToken()
        .with_identity(req.identity)
        .with_name(req.name)
        .with_grants(api.VideoGrants(room_join=True, room=req.room))
        .with_ttl(timedelta(hours=1))
        # For a NAMED agent, dispatch it explicitly instead of relying on automatic dispatch:
        # .with_room_config(
        #     api.RoomConfiguration(
        #         agents=[api.RoomAgentDispatch(agent_name="telecom-agent")]
        #     )
        # )
    )
    return TokenResponse(token=access_token.to_jwt(), url=LIVEKIT_URL, room=req.room)