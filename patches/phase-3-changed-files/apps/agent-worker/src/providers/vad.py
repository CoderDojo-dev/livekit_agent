"""Silero VAD builder (local; min_silence >= 250ms required by the audio turn detector).

One of only five files allowed to import a vendor plugin (the providers/ boundary).
"""
from __future__ import annotations

from livekit.plugins import silero


def build_vad(min_silence: float = 0.25):
    """Return a local Silero VAD instance."""
    return silero.VAD.load(min_silence_duration=min_silence)