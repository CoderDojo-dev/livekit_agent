# Cookbook 18 - French default and predictable language switching

Base: `version_96` @ `fa220abc85ed498bc83e158d6596d4510b87441f`.
Scope: the composition root's language resolution, an allow-list, a stated precedence order, and the optional Settings control. No new dependency, no new persistence system, no change to the STT/TTS provider chain.

---

## 18.1 Diagnosis

French **is** already configured as the default in every place you would expect:

- `config/settings.py`: `default_language = "fr"`, `session_language = "fr"`, `supported_languages = "fr,ar,en"`.
- `providers/language_router.py`: `LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])`.
- `config/language_presets.py`: `GREETINGS["fr"]` exists and is French.

And critically, **the STT layer cannot cause this bug.** `providers/stt.py` builds Deepgram with a single pinned `preset["deepgram_language"]`, with an explicit comment that Arabic uses the monolingual `ar` model and never `multi`. Gladia gets `languages=[one]`; Azure gets one locale. There is no multilingual detection anywhere in the STT chain, so STT cannot detect a language and cannot switch one. That rules out the largest suspect in the brief's checklist.

The wrong language is chosen *before the session starts*, in `apps/agent-worker/src/server.py`:

```python
language = settings.session_language          # "fr" - correct so far
room_name = getattr(ctx.room, "name", None)
participant = await ctx.wait_for_participant()
logger.info("agent job received room=%s language=%s", room_name, language)

user_data = await _prefetch_user_data(language, participant)
language = user_data.language                 # <-- silently replaced
...
session = build_agent_session(settings, language, keyterms)
await session.start(agent=TriageAgent(language=language), room=ctx.room)
```

and in `_prefetch_user_data`:

```python
snapshot = await get_context_client().get_snapshot(msisdn)
if snapshot is not None:
    user_data.customer_context = snapshot
    user_data.language = snapshot.preferred_language   # unconditional
```

`snapshot.preferred_language` is a CRM column, and it is assigned with:

- **no allow-list check** against `settings.languages`;
- **no precedence rule** - it outranks the configured default purely because it is assigned second;
- **no null / empty / unknown guard** - the value flows on into `GREETINGS[language]` (a `KeyError` risk) and into `TriageAgent(language=...)`.

So the session language is whatever the CRM row says. In a Tunisian telecom seed set, `preferred_language = "ar"` on some customers is entirely expected. The call "sometimes starts in Arabic" - deterministically per customer, which reads as random as soon as you change test accounts.

**This is not a bug in the intent.** `copy.profile.fields.scopeNote` documents the decision to the customer: *"The language your assistant speaks follows your account and is set when you speak to us."* The CRM value being authoritative is deliberate and must be preserved. What is missing is that it must be **validated** and **rankable**, and that the customer currently has no way to set it.

### On the mid-conversation switch to English

Nothing in the worker switches language mid-session: `SessionUserData.language` is set once and only read afterwards, and the STT/TTS chain is built once from one preset. A mid-call switch to English is therefore the **LLM ignoring its instructions**, not a state machine flipping. Read `agents/instruction_kit.py` and `agents/base_agent.py` and confirm the persona instructions contain an explicit language-lock clause. Section 18.4 gives the wording. Do not restructure the instruction kit for this - add the clause only if it is genuinely absent.

---

## 18.2 Fix - a stated precedence, in one place

New file `apps/agent-worker/src/config/language_policy.py`:

```python
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
```

### Wire it in `apps/agent-worker/src/server.py`

Add the import beside the other `config` import:

```python
from config.language_policy import resolve_session_language
```

Replace the body of `_prefetch_user_data` so the CRM value becomes a *candidate* rather than an override. `oldStr`:

```python
    snapshot = await get_context_client().get_snapshot(msisdn)
    if snapshot is not None:
        user_data.customer_context = snapshot
        user_data.language = snapshot.preferred_language
        logger.info(
            "context prefetched: customer_id=%s vip=%s",
            snapshot.customer_id,
            snapshot.is_vip,
        )
```

`newStr`:

```python
    snapshot = await get_context_client().get_snapshot(msisdn)
    if snapshot is not None:
        user_data.customer_context = snapshot
        # The caller's saved preference is a candidate, not an override. Before
        # this, an unvalidated CRM value replaced the French default outright,
        # which is why calls sometimes opened in Arabic.
        user_data.language = resolve_session_language(
            supported=settings.languages,
            default_language=settings.default_language,
            saved_preference=snapshot.preferred_language,
        )
        logger.info(
            "context prefetched: customer_id=%s vip=%s language=%s",
            snapshot.customer_id,
            snapshot.is_vip,
            user_data.language,
        )
```

And make the no-MSISDN and no-snapshot paths explicit rather than relying on the dataclass default. In `entrypoint`, `oldStr`:

```python
    language = settings.session_language
```

`newStr`:

```python
    # SESSION_LANGUAGE is a spike/console convenience; DEFAULT_LANGUAGE is the
    # platform default. Both are validated, so a bad env value cannot start a
    # call in a language with no preset.
    language = resolve_session_language(
        supported=settings.languages,
        default_language=settings.default_language,
        saved_preference=settings.session_language,
    )
```

The existing `language = user_data.language` line after the prefetch now reads an already-validated value and can stay exactly as it is.

### Also check the environment

`SESSION_LANGUAGE` and `DEFAULT_LANGUAGE` are plain env vars. Grep every env source actually loaded by the worker - `.env`, `.env.example`, `docker-compose*.yml`, `apps/agent-worker/.env` - for both names. If any of them is set to `ar` or `en`, that is a second, independent cause of the reported behaviour and the code fix will not mask it. After this cookbook a bad value is at least logged as a warning instead of applied silently.

---

## 18.3 Optional - Settings - Preferences - Preferred agent language

The brief marks this optional "if it can be done without architectural debt". It can, but **only** by writing to the existing CRM column through the existing profile write path.

### The rule that decides the design

`lib/preferences.ts` says it plainly: *"Nothing here is sent to a server, because no preferences table exists ... Every value is a pure rendering choice."* Density, text size, captions and reduce-motion are browser-local for that reason.

The agent language is **not** a rendering choice. It has to reach the worker, which reads `snapshot.preferred_language` from the CRM. So:

- **Do not** put the agent language in `lib/preferences.ts` / localStorage. A browser-local value can never reach the worker, and shipping a control that appears to work but changes nothing is exactly the fake-success behaviour section 2 of the brief forbids.
- **Do not** create a preferences table. That is the architectural debt the brief warns about.
- **Do** write `crm.customers.preferred_language` through the profile update endpoint that already backs the Profile tab's editable fields, and surface the control under Profile - Language and region, next to `copy.profile.fields.language` and its existing `scopeNote`.

### Prerequisite to verify before building the UI

Read the profile write path - `src/lib/api/me.server.ts` (or whichever server fn the Profile tab's Save uses) and the matching business-api route - and confirm whether `preferred_language` is in the allowed update field set.

- **If it is:** add the control. Use the existing `Segmented` primitive from `components/portal/primitives.tsx` with three options, add the labels to `copy.ts` under `profile.fields`, and let the existing unsaved-changes / Save / Discard machinery in `profile.tsx` handle persistence. No new state model, no new mutation pattern.
- **If it is not:** stop. Widening a write projection to accept a new column is a backend change with its own validation and audit implications, and the brief says to determine the correct next step rather than fake it. Deliver the control in a follow-up cookbook that adds `preferred_language` to the update allow-list with a server-side check against `SUPPORTED_LANGUAGES`, and note in the results file that the UI is blocked on it.

Copy to add either way:

```ts
// copy.profile.fields
agentLanguage: "Language your assistant speaks",
agentLanguageHint:
  "New conversations start in this language. You can always ask the assistant to switch during a call.",
```

Use the native names as the option labels - `Francais`, the Arabic endonym, `English` - not translated ones. The existing `scopeNote` already explains the split between the portal display language and the assistant language; keep it and place the new control directly beneath it so the distinction stays legible.

Server-side validation is mandatory whichever route you take: reject any value outside `SUPPORTED_LANGUAGES` at the API boundary. A client-side `Segmented` is a UX affordance, not a validation.

---

## 18.4 The mid-conversation switch

Read `agents/instruction_kit.py` and `agents/base_agent.py` first. If the personas already carry an explicit language lock, change nothing. If they do not, add one clause to the shared instruction block - not per agent, so a handoff cannot lose it:

> Speak only in {language}. Keep speaking {language} for the whole conversation, including after a transfer to another specialist. Change language only if the caller explicitly asks you to, for example "parle-moi en anglais", "can you speak English", "ردّ عليّ بالعربية". Do not change language because the caller uses a loanword, a foreign name, a place name, or a single foreign phrase. Do not change language because a tool result or an account record is in another language. If you are unsure whether the caller asked you to switch, keep the current language and continue.

Two notes:

- The handoff clause matters. `_on_conversation_item_added` records `type(session.current_agent).__name__`, so persona changes mid-call are real; the language instruction must survive them.
- The loanword clause matters for Tunisian French/Arabic code-switching, which is the single most likely trigger for an unrequested switch.

Because a language change is now a *request* the caller makes rather than a state the system detects, the STT preset stays pinned for the session. Honouring a mid-call switch fully - re-building STT and TTS for the new language - is a larger change to the session factory and belongs in its own cookbook. Do not attempt it here. Today the LLM will answer in the requested language while STT stays on the original; note that limitation in the results file rather than half-implementing it.

---

## 18.5 Verification

### Automated - new file `apps/business-api/../agent-worker/tests/test_language_policy.py`

Place it beside the worker's existing tests, matching their ruff conventions: no blank line after `import pytest`, double quotes, `line-length=110`.

```python
import pytest

from config.language_policy import normalise, resolve_session_language

SUPPORTED = ["fr", "ar", "en"]


def _resolve(**kwargs):
    return resolve_session_language(supported=SUPPORTED, default_language="fr", **kwargs)


def test_default_is_french_when_nothing_is_saved():
    assert _resolve() == "fr"
    assert _resolve(saved_preference=None) == "fr"
    assert _resolve(saved_preference="") == "fr"


def test_saved_preference_is_honoured_when_supported():
    assert _resolve(saved_preference="ar") == "ar"
    assert _resolve(saved_preference="en") == "en"


@pytest.mark.parametrize("value", ["de", "zz", "klingon", "  ", "1r", "f"])
def test_unsupported_saved_preference_falls_back_to_french(value):
    """A stray CRM row must not start a call in a language with no STT/TTS preset."""
    assert _resolve(saved_preference=value) == "fr"


def test_explicit_request_outranks_the_saved_preference():
    assert _resolve(saved_preference="ar", explicit_request="en") == "en"


def test_saved_preference_outranks_the_default():
    assert resolve_session_language(
        supported=SUPPORTED, default_language="fr", saved_preference="ar"
    ) == "ar"


def test_unsupported_explicit_request_does_not_win():
    """An unsupported explicit request falls through to the next candidate, not to failure."""
    assert _resolve(saved_preference="ar", explicit_request="de") == "ar"


@pytest.mark.parametrize(
    "raw,expected",
    [("fr", "fr"), ("FR", "fr"), ("fr-FR", "fr"), ("fr_FR", "fr"), (" ar ", "ar"), ("en-US", "en")],
)
def test_normalise_accepts_locale_forms(raw, expected):
    assert normalise(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "e", "eng", "3n", "-"])
def test_normalise_rejects_non_subtags(raw):
    assert normalise(raw) is None


def test_result_always_has_a_provider_preset():
    from config.language_presets import LANGUAGE_PRESETS

    for candidate in [None, "ar", "de", "", "en-GB"]:
        assert _resolve(saved_preference=candidate) in LANGUAGE_PRESETS


def test_empty_supported_list_still_yields_french():
    assert resolve_session_language(supported=[], default_language="", saved_preference=None) == "fr"
```

Run:

```bash
python -m pytest apps/agent-worker/tests/test_language_policy.py -q
ruff check apps/agent-worker/src/config/language_policy.py apps/agent-worker/src/server.py
python -m pytest apps/agent-worker -q     # no regressions in the worker suite
```

The last test is the one that matters: `resolve_session_language` can never return a code without a `LANGUAGE_PRESETS` entry, which is what makes `build_stt` / `build_tts` / `GREETINGS[...]` safe by construction.

### Live call acceptance (user, needs a microphone)

1. Customer whose CRM `preferred_language` is `fr` - greeting is French. Log line: `session language fr (source: saved preference)`.
2. Customer whose CRM value is `ar` - greeting is Arabic, and that is now **correct and intended** behaviour, logged as `source: saved preference`. Confirm this is what you want per customer; if not, the data is what needs changing, not the code.
3. Customer with no CRM value, or no MSISDN attribute - greeting is French, logged as `source: default`.
4. Temporarily set a CRM row to `de`. Expect a French greeting plus `ignoring unsupported language 'de' from saved preference`. Restore the row.
5. Speak French for several turns using loanwords and a French-pronounced place name. The agent must stay in French.
6. Say "Can you speak English?" - the agent replies in English. Say "Reviens au francais" - it returns. Note in the results file whether STT accuracy degrades, since the STT preset is still pinned to the opening language.
7. Trigger a handoff to Billing or Technical, then continue. The language must not change across the handoff.
8. End and restart the conversation. The opening language must be the same as step 1 - no leakage from the previous session's requested language.

### Definition of done for cookbook 18

- One function states the precedence: explicit request > saved preference > French.
- No language reaches the session without an allow-list check and a `LANGUAGE_PRESETS` entry.
- An unsupported value is logged and ignored, never applied.
- A call with no saved preference opens in French.
- A saved Arabic preference is honoured deliberately, not accidentally.
- Persona instructions carry an explicit language lock that survives handoffs.
- The Settings control is either shipped through the existing profile write path, or explicitly reported as blocked on widening that path - never faked with localStorage.
- Worker tests pass; ruff clean.
