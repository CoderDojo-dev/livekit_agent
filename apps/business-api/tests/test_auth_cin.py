"""The CIN digest in business-api must stay identical to the one in context-service."""
from __future__ import annotations

import hashlib
import hmac

import pytest

from business_api.infrastructure.auth import cin

_KEY = "k" * 48
_CUSTOMER = "2187de39-3a84-4c1c-872f-b6711dc9f7a1"


def test_digest_matches_pinned_vector(monkeypatch: pytest.MonkeyPatch):
    """Recomputed independently, exactly as context_service.auth_service._digest builds it."""
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", _KEY)
    expected = hmac.new(
        _KEY.encode(), f"cin_last4:{_CUSTOMER}:4821".encode(), hashlib.sha256
    ).hexdigest()
    assert cin.digest(_CUSTOMER, "4821") == expected
    # Non-digits are stripped, so "48-21" and " 4821 " verify identically.
    assert cin.digest(_CUSTOMER, "48-21") == expected
    assert cin.digest(_CUSTOMER, " 4821 ") == expected


def test_short_key_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", "tooshort")
    with pytest.raises(RuntimeError):
        cin.digest(_CUSTOMER, "4821")