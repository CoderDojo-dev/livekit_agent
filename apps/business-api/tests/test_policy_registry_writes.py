"""Safety invariants for the policy registry write path.

The registry is editable from the admin console. That is only safe because of two properties, and
these tests pin both — if either regresses, the console could start describing limits the policy
engine is not applying.

  1. Numeric thresholds are never writable. They live in POLICY_* env and are overlaid at read
     time, so `update_business_rule` accepts description and active ONLY.
  2. A GOVERNED rule (one whose thresholds come from the environment) cannot be deactivated,
     deleted, or shadowed by a new row under the same id.
"""
from __future__ import annotations

import inspect

import pytest

from business_api import policy_view
from business_api.repositories import SupervisionRepository


class _FakeScalarSession:
    """Minimal session stub: the guards below refuse before any query is issued."""

    def __init__(self, row=None):
        self._row = row
        self.deleted = []
        self.added = []

    def scalar(self, _stmt):
        return self._row

    def delete(self, row):
        self.deleted.append(row)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None


def _repo(row=None) -> SupervisionRepository:
    return SupervisionRepository(_FakeScalarSession(row))


def _governed_id() -> str:
    return next(iter(policy_view.GOVERNED_BY))


def test_governed_rules_are_declared():
    """The guards are meaningless if nothing is governed."""
    assert policy_view.GOVERNED_BY, "expected at least one POLICY_*-governed rule"


def test_update_signature_exposes_no_threshold_field():
    """The write surface must never grow a numeric threshold parameter."""
    params = set(inspect.signature(SupervisionRepository.update_business_rule).parameters)
    assert params == {"self", "rule_id", "description", "active"}


def test_create_signature_exposes_no_threshold_field():
    params = set(inspect.signature(SupervisionRepository.create_business_rule).parameters)
    assert params == {"self", "rule_id", "domain", "description"}


def test_governed_rule_cannot_be_deactivated():
    rule_id = _governed_id()

    class _Row:
        description = "x"
        active = True
        version = 1
        domain = "billing"
        definition_json: dict = {}

    _Row.rule_id = rule_id

    with pytest.raises(ValueError) as excinfo:
        _repo(_Row()).update_business_rule(rule_id, None, False)
    assert "cannot be deactivated" in str(excinfo.value)


def test_governed_rule_cannot_be_deleted():
    rule_id = _governed_id()
    with pytest.raises(ValueError) as excinfo:
        _repo().delete_business_rule(rule_id)
    assert "cannot be deleted" in str(excinfo.value)


def test_cannot_create_a_rule_under_a_governed_id():
    """Otherwise the overlay would attach live enforced numbers to a fabricated rule."""
    rule_id = _governed_id()
    with pytest.raises(ValueError) as excinfo:
        _repo().create_business_rule(rule_id, "billing", "fake")
    assert "governed rule id" in str(excinfo.value)


def test_create_requires_a_rule_id():
    with pytest.raises(ValueError):
        _repo().create_business_rule("   ", "billing", None)


def test_ungoverned_rule_may_be_deactivated():
    """The whole point: a catalog rule IS editable."""

    class _Row:
        rule_id = "RULE_NOT_GOVERNED_BY_ENV"
        description = "before"
        active = True
        version = 3
        domain = "general"
        definition_json: dict = {}

    row = _Row()
    result = _repo(row).update_business_rule(row.rule_id, "after", False)

    assert result is not None
    assert result["active"] is False
    assert result["description"] == "after"
    # A versioned registry: a real change must move the version.
    assert result["version"] == 4
    assert result["changed"] is True


def test_no_op_update_does_not_bump_the_version():
    """A PATCH that changes nothing must not pad the version or the audit trail."""

    class _Row:
        rule_id = "RULE_NOT_GOVERNED_BY_ENV"
        description = "same"
        active = True
        version = 7
        domain = "general"
        definition_json: dict = {}

    row = _Row()
    result = _repo(row).update_business_rule(row.rule_id, "same", True)

    assert result["changed"] is False
    assert result["version"] == 7


def test_update_returns_none_for_a_missing_rule():
    assert _repo(None).update_business_rule("RULE_DOES_NOT_EXIST", "x", None) is None


def test_delete_returns_false_for_a_missing_rule():
    assert _repo(None).delete_business_rule("RULE_DOES_NOT_EXIST") is False
