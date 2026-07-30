"""La liste de keyterms doit rester courte, anglaise et sans marque."""
import re

from config.keyterms import MAX_KEYTERMS, TELECOM_KEYTERMS, keyterms_for

_ALLOWED = re.compile(r"^[A-Za-z0-9-]+$")
# Mots francais et marques: interdits par construction, pas par convention.
_FORBIDDEN = (
    "facture", "solde", "recharge", "forfait", "dinars", "millimes",
    "orange", "mobicash", "saha", "anaqui", "dial", "win", "mawassal",
    "tunisie", "telecom", "flexi", "ahla", "elissa", "hayya", "tawfir",
)


def test_list_is_short():
    assert 0 < len(TELECOM_KEYTERMS) <= MAX_KEYTERMS


def test_every_term_is_ascii_technical():
    for term in TELECOM_KEYTERMS:
        assert _ALLOWED.match(term), term


def test_no_french_word_and_no_brand():
    lowered = [t.lower() for t in TELECOM_KEYTERMS]
    for banned in _FORBIDDEN:
        assert banned not in lowered, banned


def test_observed_failures_are_covered():
    lowered = [t.lower() for t in TELECOM_KEYTERMS]
    for term in ("roaming", "wifi", "data", "hotspot"):
        assert term in lowered


def test_keyterms_for_dedupes_and_caps():
    out = keyterms_for(["roaming", "ROAMING", "eSIM"])
    assert len(out) == len(set(t.lower() for t in out))
    assert len(out) <= MAX_KEYTERMS
