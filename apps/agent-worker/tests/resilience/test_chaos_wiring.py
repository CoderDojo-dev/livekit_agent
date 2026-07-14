"""Offline guard for the resilience + routing wiring (cookbook section 16).

No keys, no network, no live call: asserts the chaos toggle forces an invalid primary model
(so the live console run will fail the primary and fall over to the secondary), that the
settings expose a per-kind flag, and that Arabic routes to language="ar" (never "multi").
The full live failover is the manual console demo described in the phase notes.
"""
from __future__ import annotations

from types import SimpleNamespace
from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from providers._resilience import INVALID_MODEL, SessionResilienceMonitor, chaos_model, monitor_room_resilience


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


def test_room_resilience_monitor_handlers() -> None:
    listeners = {}

    class FakeRoom:
        name = "test-room"
        def on(self, event, cb):
            listeners[event] = cb

    user_data = SimpleNamespace()
    monitor = monitor_room_resilience(FakeRoom(), session=None, user_data=user_data)
    assert isinstance(monitor, SessionResilienceMonitor)

    # Test reconnecting
    listeners["reconnecting"]()
    assert getattr(user_data, "is_reconnecting") is True

    # Test reconnected
    listeners["reconnected"]()
    assert getattr(user_data, "is_reconnecting") is False

    # Test degraded quality
    listeners["connection_quality_changed"]("caller-1", "POOR")
    assert getattr(user_data, "webrtc_degraded") is True

    # Test token expired disconnect
    listeners["disconnected"](SimpleNamespace(name="TOKEN_EXPIRED"))
    assert getattr(user_data, "token_expired") is True
