"""Offline tests for the integrity summary (no DB)."""
from __future__ import annotations

from business_api.jobs.integrity import summarize


def test_summarize_clean() -> None:
    assert summarize({"a->b": 0, "c->d": 0}, audit_chain_intact=True) is True


def test_summarize_detects_orphans() -> None:
    assert summarize({"a->b": 3}, audit_chain_intact=True) is False


def test_summarize_detects_broken_chain() -> None:
    assert summarize({"a->b": 0}, audit_chain_intact=False) is False