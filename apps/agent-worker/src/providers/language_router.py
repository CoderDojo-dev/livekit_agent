"""Route per-turn language to the decided STT/TTS chain (Blueprint section 13)."""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS


class LanguageRouter:
    """Resolve the STT/TTS preset for a detected/selected language."""

    def preset_for(self, language: str) -> dict[str, str]:
        """Return the provider preset for ``language`` (defaults to French)."""
        return LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])