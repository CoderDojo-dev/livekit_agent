"""The registry must report the LIVE enforced thresholds, never a stale seeded literal."""
from __future__ import annotations

import importlib

import pytest


def _fresh(monkeypatch, **env):
    """Reload policy_view under a specific POLICY_* environment (module reads os.getenv at call)."""
    for key in (
        "POLICY_PAYMENT_CAP_TND",
        "POLICY_DEFERRAL_MIN_AGE_DAYS",
        "POLICY_DEFERRAL_MAX_PER_YEAR",
        "POLICY_DEFERRAL_UNPAID_THRESHOLD_TND",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import business_api.policy_view as pv

    return importlib.reload(pv)


def test_defaults_match_enforcer(monkeypatch):
    """With no env set, the projection equals the policy-service defaults (200 / 180 / 2 / 150)."""
    pv = _fresh(monkeypatch)
    defs = pv.enforced_definitions()
    assert defs["RULE_BILLING_CAP"] == {"max_payment_tnd": 200.0}
    assert defs["RULE_DEFERRAL_ELIGIBILITY"] == {
        "min_account_age_days": 180,
        "max_deferrals_per_year": 2,
        "unpaid_review_threshold_tnd": 150.0,
    }


def test_env_override_is_reported(monkeypatch):
    """A raised cap in env is what the registry reports - no drift from the enforced value."""
    pv = _fresh(monkeypatch, POLICY_PAYMENT_CAP_TND="500")
    assert pv.enforced_definitions()["RULE_BILLING_CAP"] == {"max_payment_tnd": 500.0}


def test_overlay_replaces_seeded_literal(monkeypatch):
    """A governed rule's definition is replaced by enforced numbers, flagged and sourced."""
    pv = _fresh(monkeypatch, POLICY_PAYMENT_CAP_TND="500")
    seeded = [
        {"rule_id": "RULE_BILLING_CAP", "domain": "billing", "version": 1, "active": True,
         "description": "cap", "definition": {"max_payment_tnd": 200}},  # stale literal
        {"rule_id": "RULE_IDENTITY_REQUIRED", "domain": "identity", "version": 1, "active": True,
         "description": "id", "definition": {}},
    ]
    out = {r["rule_id"]: r for r in pv.overlay(seeded)}
    cap = out["RULE_BILLING_CAP"]
    assert cap["definition"] == {"max_payment_tnd": 500.0}
    assert cap["enforced"] is True
    assert cap["governed_by"] == ["POLICY_PAYMENT_CAP_TND"]
    assert cap["source"]
    # Non-governed rules pass through, flagged not-enforced, definition untouched.
    assert out["RULE_IDENTITY_REQUIRED"]["enforced"] is False
    assert out["RULE_IDENTITY_REQUIRED"]["definition"] == {}


def test_deferral_registry_is_complete(monkeypatch):
    """The unpaid-review threshold that was missing from the seed is present in the projection."""
    pv = _fresh(monkeypatch)
    deferral = pv.enforced_definitions()["RULE_DEFERRAL_ELIGIBILITY"]
    assert "unpaid_review_threshold_tnd" in deferral


def test_malformed_override_falls_back(monkeypatch):
    """A non-numeric override must not crash the admin view; it reports the enforced default."""
    pv = _fresh(monkeypatch, POLICY_PAYMENT_CAP_TND="not-a-number")
    assert pv.enforced_definitions()["RULE_BILLING_CAP"] == {"max_payment_tnd": 200.0}
