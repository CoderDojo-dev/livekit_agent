"""Offline test: the minted token carries the room-join grant for the requested room."""
from __future__ import annotations

import os

os.environ.setdefault("LIVEKIT_API_KEY", "devkey")
os.environ.setdefault("LIVEKIT_API_SECRET", "devsecret_change_me_please_32chars_min")

import jwt  # provided by livekit-api
from livekit import api


def test_token_has_room_join_grant() -> None:
    token = (
        api.AccessToken()
        .with_identity("caller-1")
        .with_grants(api.VideoGrants(room_join=True, room="telecom-support"))
        .to_jwt()
    )
    claims = jwt.decode(token, os.environ["LIVEKIT_API_SECRET"], algorithms=["HS256"])
    assert claims["sub"] == "caller-1"
    assert claims["video"]["room"] == "telecom-support"
    assert claims["video"]["roomJoin"] is True