"""Enforced-threshold projection for the Policy rule registry (spec section 17 governance view).

The deterministic policy engine (policy-service) is twelve-factor: it reads its numeric thresholds
from ``POLICY_*`` environment variables, never from a table. The ``reference.business_rules`` table
is the governance record (rule id, domain, description, version, active) - it must NOT carry its own
copy of those numbers, or the registry a supervisor reviews can silently drift from what is actually
enforced (e.g. the table says cap 200 while ``POLICY_PAYMENT_CAP_TND=500`` is enforced).

This module removes that drift by construction: the business-api reads the SAME ``POLICY_*`` env the
engine reads (both containers load the same ``.env`` via ``env_file``) and overlays the live enforced
numbers onto each governed rule at read time. There is exactly one source of truth for the values -
the environment - and the registry reports it rather than a stale literal.

The defaults below MUST match ``policy_service.config.PolicyThresholds``. ``tests/test_policy_view.py``
pins them so the two cannot silently diverge.
"""
from __future__ import annotations

import os

# Same aliases + defaults as policy_service.config.PolicyThresholds (the enforcer).
_PAYMENT_CAP_ENV = "POLICY_PAYMENT_CAP_TND"
_DEFERRAL_MIN_AGE_ENV = "POLICY_DEFERRAL_MIN_AGE_DAYS"
_DEFERRAL_MAX_PER_YEAR_ENV = "POLICY_DEFERRAL_MAX_PER_YEAR"
_DEFERRAL_UNPAID_ENV = "POLICY_DEFERRAL_UNPAID_THRESHOLD_TND"

_DEFAULTS = {
    _PAYMENT_CAP_ENV: 200.0,
    _DEFERRAL_MIN_AGE_ENV: 180,
    _DEFERRAL_MAX_PER_YEAR_ENV: 2,
    _DEFERRAL_UNPAID_ENV: 150.0,
}

# The env var(s) that govern each registry rule id. Rules that carry no numeric threshold are absent.
GOVERNED_BY: dict[str, list[str]] = {
    "RULE_BILLING_CAP": [_PAYMENT_CAP_ENV],
    "RULE_DEFERRAL_ELIGIBILITY": [
        _DEFERRAL_MIN_AGE_ENV,
        _DEFERRAL_MAX_PER_YEAR_ENV,
        _DEFERRAL_UNPAID_ENV,
    ],
}

_SOURCE = "policy-engine (POLICY_* env)"


def _num(env_name: str) -> float | int:
    """Read a POLICY_* value from the environment, falling back to the enforcer's default."""
    default = _DEFAULTS[env_name]
    raw = os.getenv(env_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw) if isinstance(default, int) else float(raw)
    except ValueError:
        # A malformed override should not crash the admin view; report the enforced default.
        return default


def enforced_definitions() -> dict[str, dict]:
    """Live enforced thresholds, keyed by registry rule id - what the engine actually applies now."""
    return {
        "RULE_BILLING_CAP": {"max_payment_tnd": _num(_PAYMENT_CAP_ENV)},
        "RULE_DEFERRAL_ELIGIBILITY": {
            "min_account_age_days": _num(_DEFERRAL_MIN_AGE_ENV),
            "max_deferrals_per_year": _num(_DEFERRAL_MAX_PER_YEAR_ENV),
            "unpaid_review_threshold_tnd": _num(_DEFERRAL_UNPAID_ENV),
        },
    }


def overlay(rules: list[dict]) -> list[dict]:
    """Return the registry rows with governed thresholds replaced by the live enforced values.

    A governed rule's ``definition`` becomes the enforced numbers (not the seeded literal), plus
    ``enforced=True``, the ``governed_by`` env var(s), and the ``source``. Non-governed rules pass
    through with ``enforced=False`` so the dashboard can render them plainly.
    """
    enforced = enforced_definitions()
    out: list[dict] = []
    for rule in rules:
        row = dict(rule)
        rule_id = row.get("rule_id")
        if rule_id in enforced:
            row["definition"] = enforced[rule_id]
            row["enforced"] = True
            row["governed_by"] = GOVERNED_BY[rule_id]
            row["source"] = _SOURCE
        else:
            row["enforced"] = False
        out.append(row)
    return out
