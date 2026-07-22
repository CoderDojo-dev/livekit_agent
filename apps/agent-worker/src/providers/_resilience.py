"""Shared resilience helper: the chaos toggle used by each provider builder (cookbook section 16).

Keeping the swap in one tiny module means the three builders apply it identically and there
is a single definition of the deliberately invalid model id.
"""
from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

logger = logging.getLogger(__name__)

# A deliberately invalid model id used to force a primary failure in chaos runs.
INVALID_MODEL = "chaos-invalid-model-does-not-exist"


def chaos_model(real_model: str, break_primary: bool) -> str:
    """Return ``real_model``, or the invalid id when ``break_primary`` is set."""
    return INVALID_MODEL if break_primary else real_model


class SessionResilienceMonitor:
    """Explicit WebRTC and LiveKit room recovery monitor (tokens, disconnects, packet loss, reconnect)."""

    def __init__(self, room: object, session: object | None = None, user_data: Any = None) -> None:
        self.room = room
        self.session = session
        self.user_data = user_data
        self._reconnecting = False

    def attach(self) -> SessionResilienceMonitor:
        """Attach room event listeners for recovery flows."""
        on_event = getattr(self.room, "on", None)
        if not callable(on_event):
            return self

        with suppress(Exception):
            on_event("reconnecting", self._on_reconnecting)
            on_event("reconnected", self._on_reconnected)
            on_event("disconnected", self._on_disconnected)
            on_event("connection_quality_changed", self._on_connection_quality_changed)
        return self

    def _on_reconnecting(self) -> None:
        self._reconnecting = True
        if self.user_data is not None:
            with suppress(Exception):
                self.user_data.is_reconnecting = True
        logger.warning("LiveKit room=%s temporary disconnect; initiating reconnect flow...", getattr(self.room, "name", "unknown"))
        with suppress(Exception):
            from observability_kit import incr_fallback
            incr_fallback("webrtc_reconnecting")

    def _on_reconnected(self) -> None:
        self._reconnecting = False
        if self.user_data is not None:
            with suppress(Exception):
                self.user_data.is_reconnecting = False
        logger.info("LiveKit room=%s successfully reconnected after temporary interruption", getattr(self.room, "name", "unknown"))
        if self.session is not None and hasattr(self.session, "say"):
            with suppress(Exception):
                import asyncio
                _APOLOGY = {
                    "fr": "Désolé pour cette brève interruption. Je suis de nouveau avec vous.",
                    "ar": "نعتذر عن الانقطاع القصير. أنا معك الآن من جديد.",
                    "en": "Sorry for the brief connection interruption. I am right here.",
                }
                _lang = getattr(self.user_data, "language", "fr")
                _code = str(getattr(_lang, "value", _lang) or "fr").lower().strip()[:2]
                self._apology_task = asyncio.create_task(self.session.say(_APOLOGY.get(_code, _APOLOGY["fr"])))

    def _on_disconnected(self, reason: object | None = None) -> None:
        room_name = getattr(self.room, "name", "unknown")
        reason_str = str(reason or "").lower()
        if "token" in reason_str or "expired" in reason_str or "jwt" in reason_str or getattr(reason, "name", "") == "TOKEN_EXPIRED":
            logger.error("LiveKit room=%s disconnected due to EXPIRED ACCESS TOKEN: %s. Initiating token recovery / session teardown.", room_name, reason)
            if self.user_data is not None:
                with suppress(Exception):
                    self.user_data.token_expired = True
            with suppress(Exception):
                from observability_kit import incr_fallback
                incr_fallback("webrtc_token_expired")
        else:
            logger.warning("LiveKit room=%s permanently disconnected: %s", room_name, reason)
            with suppress(Exception):
                from observability_kit import incr_fallback
                incr_fallback("webrtc_disconnected")

    def _on_connection_quality_changed(self, participant: object, quality: object) -> None:
        quality_str = str(getattr(quality, "name", quality)).upper()
        if quality_str in {"POOR", "LOST", "2", "3"}:
            logger.warning("Degraded WebRTC session / packet loss detected for participant=%s (quality=%s in room=%s)", getattr(participant, "identity", participant), quality_str, getattr(self.room, "name", "unknown"))
            with suppress(Exception):
                from observability_kit import incr_fallback
                incr_fallback("webrtc_degraded")
            if self.user_data is not None:
                with suppress(Exception):
                    self.user_data.webrtc_degraded = True


def monitor_room_resilience(room: object, session: object | None = None, user_data: object | None = None) -> SessionResilienceMonitor:
    """Instantiate and attach a SessionResilienceMonitor to `room`."""
    return SessionResilienceMonitor(room, session, user_data).attach()
