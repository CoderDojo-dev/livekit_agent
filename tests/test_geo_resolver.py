"""Contrat de normalisation : il doit rester identique au seeder."""
import pytest

from nms_sim.geo_resolver import normalize, resolve


@pytest.mark.parametrize("raw,expected", [
    ("Ariana", "ariana"),
    ("  ARIANA  ", "ariana"),
    ("El Ariana", "ariana"),
    ("L'Ariana", "ariana"),
    ("Beja", "beja"),
    ("Gabes", "gabes"),
    ("Ben  Arous", "ben arous"),
    ("", ""),
])
def test_normalize_is_deterministic(raw, expected):
    assert normalize(raw) == expected


def test_resolve_returns_none_for_unknown_place(session):
    assert resolve(session, "Atlantide") is None


def test_resolve_handles_misspelling(session):
    match = resolve(session, "Metlaouii")
    assert match is not None
    assert match.area_code == "TN-71-METLAOUI"
    assert match.exact is False
