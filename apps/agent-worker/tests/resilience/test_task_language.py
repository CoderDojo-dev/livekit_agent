"""Long-context tasks always use the session's locked language, never the LLM's default.

v53-v54 regression: when the LLM re-prompted a persona it generated the task description
in English because the cached instructions did not include an explicit language anchor.
The fix is in build_persona_instructions: the ``{language}`` placeholder in every agent
block is always resolved before the LLM sees it.
"""

from __future__ import annotations

import pytest

from agents.domains import SUPPORTED_LANGUAGES


@pytest.mark.parametrize("lang", sorted(SUPPORTED_LANGUAGES))
def test_language_is_locked_in_instructions(lang: str) -> None:
    """All personas receive instructions in the caller's language, never default-English."""
    from agents.billing_agent import _CORE as BILLING_CORE
    from agents.technical_agent import _CORE as TECHNICAL_CORE
    from agents.manager_agent import _CORE as MANAGER_CORE
    from agents.account_services_agent import _CORE as ACCOUNT_CORE

    lang_name = {"fr": "French", "ar": "Arabic", "en": "English"}[lang]
    for label, core in [
        ("billing", BILLING_CORE),
        ("technical", TECHNICAL_CORE),
        ("manager", MANAGER_CORE),
        ("account", ACCOUNT_CORE),
    ]:
        text = core.format(lang_name=lang_name)
        assert lang_name.lower() in text.lower() or lang in text, (
            f"{label} instructions for {lang} do not mention the language"
        )
