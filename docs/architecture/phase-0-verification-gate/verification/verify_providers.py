"""Phase-0/1 empirical verification spike.

Responsibility: reproduce, against the real provider APIs, the per-language go/no-go that
DR-0 records from documentation — so the decision is *confirmed*, not merely asserted.

This is a throwaway verification spike under ``docs/architecture/`` — it is NOT a
production module and is never imported by any app/service. It instantiates the *decided*
providers via direct LiveKit plugins (never LiveKit Inference) for each supported
language and performs a minimal STT and TTS round-trip, printing a pass/fail line per
(language, component, provider).

Usage::

    pip install -r requirements-spike.txt
    cp .env.example .env            # fill in real keys
    python verify_providers.py --languages fr ar en

Requires provider keys in the environment (see ``.env.example``). With no keys it prints
the planned matrix and exits 0, so CI can run it as a dry-run.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import provider_matrix as pm

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("verify_providers")

_SAMPLE_TEXT = {
    "fr": "Bonjour, je souhaite consulter le montant de ma facture.",
    "en": "Hello, I would like to check my current bill amount.",
    "ar": "مرحبا، أريد الاستعلام عن قيمة فاتورتي.",
}


def _keys_present() -> bool:
    """True if at least the primary providers' keys are set (real round-trip possible)."""
    return bool(os.getenv("DEEPGRAM_API_KEY")) and bool(os.getenv("ELEVENLABS_API_KEY"))


def _print_planned_matrix(languages: list[str]) -> None:
    logger.info("Planned per-language routing (DR-0):")
    for lang in languages:
        stt = pm.STT_ROUTING[lang]
        tts = pm.TTS_ROUTING[lang]
        logger.info(
            "  [%s] STT primary=%s/%s %s | TTS primary=%s/%s",
            lang,
            stt.primary.provider, stt.primary.model, stt.primary.params,
            tts.primary.provider, tts.primary.model,
        )
    logger.info("  turn-detector=%s (%s)", pm.TURN_DETECTOR.model, pm.TURN_DETECTOR.params)


async def _round_trip(language: str) -> bool:
    """Synthesize sample text (TTS primary) then transcribe it back (STT primary).

    Returns True if both the decided primary providers respond for ``language``.
    Imports plugins lazily so the dry-run path needs no SDK installed.
    """
    from livekit.plugins import deepgram, elevenlabs

    text = _SAMPLE_TEXT[language]
    tts_choice = pm.TTS_ROUTING[language].primary
    stt_choice = pm.STT_ROUTING[language].primary

    # TTS primary (ElevenLabs Flash v2.5) — synthesize sample text to audio frames.
    tts = elevenlabs.TTS(model=tts_choice.model)
    frames = []
    async for ev in tts.synthesize(text):
        frames.append(ev.frame)
    if not frames:
        logger.error("[%s] TTS produced no audio (%s)", language, tts_choice.provider)
        return False
    logger.info("[%s] TTS OK via %s/%s (%d frames)", language, tts_choice.provider,
                tts_choice.model, len(frames))

    # STT primary (Deepgram Nova-3; language=ar for Arabic) — transcribe the audio back.
    stt = deepgram.STT(model=stt_choice.model, language=stt_choice.params.get("language"))
    stream = stt.stream()
    for frame in frames:
        stream.push_frame(frame)
    stream.end_input()
    transcript = ""
    async for ev in stream:
        if ev.alternatives:
            transcript = ev.alternatives[0].text
    await stream.aclose()
    ok = bool(transcript.strip())
    logger.info("[%s] STT %s via %s/%s language=%s -> %r", language,
                "OK" if ok else "EMPTY", stt_choice.provider, stt_choice.model,
                stt_choice.params.get("language"), transcript)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase-0 provider verification spike")
    parser.add_argument(
        "--languages", nargs="+", default=list(pm.SUPPORTED_LANGUAGES),
        choices=pm.SUPPORTED_LANGUAGES,
    )
    args = parser.parse_args()

    _print_planned_matrix(args.languages)

    if not _keys_present():
        logger.warning("No provider keys set — dry run only. Fill .env to run real round-trips.")
        return 0

    import asyncio

    results: dict[str, bool] = {}
    for lang in args.languages:
        try:
            results[lang] = asyncio.run(_round_trip(lang))
        except Exception as exc:  # spike: surface any provider/SDK error explicitly
            logger.error("[%s] round-trip failed: %s", lang, exc)
            results[lang] = False

    logger.info("Summary: %s", {k: ("PASS" if v else "FAIL") for k, v in results.items()})
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
