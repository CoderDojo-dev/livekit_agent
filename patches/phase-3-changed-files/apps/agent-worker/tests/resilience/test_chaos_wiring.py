"""Offline guard for the resilience + routing wiring (cookbook section 16).

No keys, no network, no live call: asserts the chaos toggle forces an invalid primary model
(so the live console run will fail the primary and fall over to the secondary), that the
settings expose a per-kind flag, and that Arabic routes to language="ar" (never "multi").
The full live failover is the manual console demo described in the phase notes.
"""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from providers._resilience import INVALID_MODEL, chaos_model


def test_chaos_flag_breaks_primary_model() -> None:
    assert chaos_model("gpt-4.1-mini", True) == INVALID_MODEL


def test_no_chaos_keeps_real_model() -> None:
    assert chaos_model("gpt-4.1-mini", False) == "gpt-4.1-mini"


def test_settings_expose_a_chaos_flag_per_provider_kind() -> None:
    settings = Settings(_env_file=None)
    for kind in ("stt", "llm", "tts"):
        assert hasattr(settings, f"chaos_break_{kind}")


def test_arabic_routes_to_language_ar() -> None:
    assert LANGUAGE_PRESETS["ar"]["deepgram_language"] == "ar"