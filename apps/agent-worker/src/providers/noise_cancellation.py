"""Noise-cancellation builder (the providers/ vendor boundary; cookbook section 6).

[VERIFY] BVC may require livekit-plugins-noise-cancellation and, for some models, LiveKit
Cloud. Returns None when disabled so console/self-hosted runs never hard-depend on it.
Confirm at docs.livekit.io/agents/build/audio/ before enabling for telephony.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_noise_cancellation(enabled: bool):
    """Return a BVC noise-cancellation plugin instance, or None when disabled/unavailable."""
    if not enabled:
        return None
    try:
        from livekit.plugins import noise_cancellation

        return noise_cancellation.BVC()
    except Exception as exc:
        logger.warning("noise cancellation requested but unavailable: %s", exc)
        return None