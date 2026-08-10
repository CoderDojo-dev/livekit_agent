"""scrypt hashing: round trip, rejection, and tolerance of corrupt records."""
from __future__ import annotations

from business_api.infrastructure.auth import passwords


def test_round_trip():
    algorithm, params, encoded = passwords.hash_password("correct horse battery")
    assert algorithm == "scrypt"
    assert passwords.verify_password("correct horse battery", algorithm, params, encoded)


def test_wrong_password_is_rejected():
    algorithm, params, encoded = passwords.hash_password("correct horse battery")
    assert not passwords.verify_password("Correct horse battery", algorithm, params, encoded)


def test_salt_is_unique_per_hash():
    _, _, first = passwords.hash_password("same password")
    _, _, second = passwords.hash_password("same password")
    assert first != second


def test_unknown_algorithm_is_rejected_not_raised():
    _, params, encoded = passwords.hash_password("whatever")
    assert passwords.verify_password("whatever", "bcrypt", params, encoded) is False


def test_corrupt_record_returns_false():
    for encoded in ("", "nodollar", "zz$zz", "$"):
        assert passwords.verify_password("x", "scrypt", passwords.default_params(), encoded) is False