"""Offline consistency tests for the Phase-0 decision matrix (DR-0).

These tests use NO LiveKit/vendor SDK objects, no network and no API keys. They prove
the *decision* is internally complete and consistent — the meaningful "test" for a
verification-gate phase. Run with:  pytest -q docs/architecture/phase-0-verification-gate/verification
"""

from __future__ import annotations

import provider_matrix as pm


def test_every_supported_language_has_stt_and_tts() -> None:
    """CDC §2.4: all three languages must have an STT and a TTS chain."""
    for lang in pm.SUPPORTED_LANGUAGES:
        assert lang in pm.STT_ROUTING, f"missing STT chain for {lang}"
        assert lang in pm.TTS_ROUTING, f"missing TTS chain for {lang}"


def test_every_chain_has_fallback() -> None:
    """Blueprint §1: provider redundancy wired from day one — primary + >=1 fallback."""
    chains = list(pm.STT_ROUTING.values()) + list(pm.TTS_ROUTING.values()) + [pm.LLM_CHAIN]
    for chain in chains:
        assert len(chain.fallbacks) >= 1, "every chain needs at least one fallback"
        # primary and fallbacks must be distinct providers (true redundancy)
        providers = [c.provider for c in chain.all_choices()]
        assert len(set(providers)) >= 2, f"fallback shares provider with primary: {providers}"


def test_no_provider_used_outside_verified_language_support() -> None:
    """No pick may claim a language the provider is not doc-verified to support."""
    for lang, chain in pm.STT_ROUTING.items():
        for choice in chain.all_choices():
            assert pm.is_supported(choice.provider, "stt", lang), (
                f"{choice.provider} STT not verified for {lang}"
            )
    for lang, chain in pm.TTS_ROUTING.items():
        for choice in chain.all_choices():
            assert pm.is_supported(choice.provider, "tts", lang), (
                f"{choice.provider} TTS not verified for {lang}"
            )


def test_arabic_stt_does_not_rely_on_deepgram_multi() -> None:
    """Key verified constraint: Arabic is absent from Deepgram 'multi'; must use language=ar."""
    ar_primary = pm.STT_ROUTING["ar"].primary
    assert ar_primary.provider == "deepgram"
    assert ar_primary.params.get("language") == "ar", "Arabic STT must pin language=ar, not multi"


def test_turn_detector_covers_all_languages() -> None:
    """The audio turn detector must cover FR/AR/EN (text model lacks Arabic)."""
    for lang in pm.SUPPORTED_LANGUAGES:
        assert lang in pm.TURN_DETECTOR_LANGUAGES, f"turn detector missing {lang}"
    assert pm.VAD.params.get("min_silence_s") == "0.25", "VAD must satisfy >=250ms for the EOU model"


def test_every_choice_carries_a_verification_source() -> None:
    """Exit criterion: every per-language pick names its verification source."""
    chains = list(pm.STT_ROUTING.values()) + list(pm.TTS_ROUTING.values()) + [pm.LLM_CHAIN]
    for chain in chains:
        for choice in chain.all_choices():
            assert choice.source.startswith("http"), f"{choice.provider}/{choice.model} lacks a source"
    assert pm.TURN_DETECTOR.source.startswith("http")
