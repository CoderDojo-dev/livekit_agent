"""[VERIFY] Audio-native turn detector — isolates the one moving SDK symbol.

DR-0 decided the audio EOU model (FR/AR/EN, local CPU for self-hosted). The exact symbol
(`livekit.agents.inference.TurnDetector`) is fast-moving; confirm at build time against
docs.livekit.io/agents/build/turns/turn-detector/. Fallback if the symbol differs: text
MultilingualModel for fr/en + STT-language/VAD for ar, or turn_detection="stt".
"""
from __future__ import annotations


def build_turn_detector():
    """Return the audio-native turn detector (Phase 3)."""
    raise NotImplementedError("wired in Phase 3; see VERIFY note above")