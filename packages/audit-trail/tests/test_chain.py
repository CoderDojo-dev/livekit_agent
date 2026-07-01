"""Offline tests for the hash-chain primitives (no DB)."""
from __future__ import annotations

from audit_trail import AuditLedger, build_entry, compute_entry_hash, verify_chain
from audit_trail.ledger import GENESIS_HASH


def test_compute_entry_hash_is_deterministic() -> None:
    a = compute_entry_hash(GENESIS_HASH, {"b": 2, "a": 1}, "2026-06-29T00:00:00+00:00")
    b = compute_entry_hash(GENESIS_HASH, {"a": 1, "b": 2}, "2026-06-29T00:00:00+00:00")
    assert a == b  # canonical (key-sorted) payload


def test_ledger_chain_is_intact() -> None:
    ledger = AuditLedger()
    ledger.append("s1", "policy_verdict", {"verdict": "AUTHORIZED"})
    ledger.append("s1", "execution_result", {"reference": "PAY-1"})
    assert ledger.verify() is True
    assert len(ledger.entries) == 2


def test_tamper_breaks_the_chain() -> None:
    e1 = build_entry("1", "s", "policy_verdict", {"verdict": "REFUSED"}, GENESIS_HASH)
    e2 = build_entry("2", "s", "execution_result", {"ref": "X"}, e1.entry_hash)
    assert verify_chain([e1, e2]) is True
    tampered = e1.__class__(**{**e1.__dict__, "payload": {"verdict": "AUTHORIZED"}})
    assert verify_chain([tampered, e2]) is False