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