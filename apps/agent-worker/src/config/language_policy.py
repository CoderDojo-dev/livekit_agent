"""Session language resolution. One function, one stated precedence order.

Before this module the session language was whatever was assigned last: the
configured default, then unconditionally overwritten by the CRM's
preferred_language with no validation. An unsupported or empty CRM value
reached GREETINGS[...] and TriageAgent(language=...) directly.

Precedence, highest first:

  1. an explicit in-conversation request from the caller ('parle-moi en
     anglais') - applied at runtime, never at session start;
  2. the caller's saved preference (crm.customers.preferred_language);
  3. DEFAULT_LANGUAGE, which is French.

Only languages in SUPPORTED_LANGUAGES are ever returned. An unsupported value
is ignored rather than honoured, so a stray CRM row cannot start a call in a
language the platform has no STT/TTS preset for.
"""

from __future__ import annotations

import logging

from config.language_presets import LANGUAGE_PRESETS

logger = logging.getLogger(__name__)


def normalise(language: str | None) -> str | None:
    """Reduce a raw language value to a bare lowercase ISO-639-1 subtag.

    Accepts 'fr', 'FR', 'fr-FR', 'fr_FR', ' fr ' and returns 'fr'. Returns None
    for anything that is not a two-letter subtag, including '' and None.
    """
    if not language:
        return None
    subtag = str(language).strip().lower().replace("_", "-").split("-")[0]
    return subtag if len(subtag) == 2 and subtag.isalpha() else None


def resolve_session_language(
    *,
    supported: list[str],
    default_language: str,
    saved_preference: str | None = None,
    explicit_request: str | None = None,
) -> str:
    """Return the language a session must start in.

    Every candidate is normalised and checked against ``supported``. The first
    supported candidate wins. If nothing is supported, fall back to
    ``default_language``, then to 'fr', which always has a preset.
    """
    allowed = [code for code in (normalise(item) for item in supported) if code]
    if not allowed:
        allowed = ["fr"]

    for label, candidate in (
        ("explicit request", explicit_request),
        ("saved preference", saved_preference),
        ("default", default_language),
    ):
        code = normalise(candidate)
        if code is None:
            continue
        if code in allowed and code in LANGUAGE_PRESETS:
            logger.info("session language %s (source: %s)", code, label)
            return code
        logger.warning(
            "ignoring unsupported language %r from %s; supported=%s",
            candidate,
            label,
            allowed,
        )

    fallback = normalise(default_language)
    if fallback and fallback in LANGUAGE_PRESETS:
        return fallback
    return "fr"
