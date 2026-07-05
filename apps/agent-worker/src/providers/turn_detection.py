"""Turn-detection builder and main-process runner registration.

`register_inference_runners()` must be called at import time in the main
process so that turn-detector models are available when job subprocesses
start (fixes "no inference executor" crash).

`build_turn_detector()` returns the configured turn-detection strategy.
"""
from __future__ import annotations

from livekit.agents import inference

from config import get_settings


def register_inference_runners() -> None:
    """Register TurnDetector inference runner in the main process.

    Must be called at module import in server.py before any jobs start.
    Without this call, job subprocesses will crash with "no inference executor"
    because the turn-detector model was never registered.
    """
    inference.TurnDetector()


def build_turn_detector():
    """Return the configured turn-detection strategy based on TURN_DETECTION_MODE."""
    mode = get_settings().turn_detection_mode

    if mode == "vad":
        from livekit.plugins import silero
        return silero.VAD.load()

    if mode == "multilingual":
        from livekit.plugins.turn_detector.multilingual import MultilingualModel
        return MultilingualModel()

    return "stt"
