"""Duplicate window: a just-executed action replays; after the window it is a new action."""
import time

from session.session_state import _DUPLICATE_WINDOW_S, SessionUserData


def _ud():
    return SessionUserData(session_id="s1")

def test_retry_before_success_reuses_key():
    ud = _ud()
    assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == \
           ud.new_idempotency_key("TOP_UP", {"amount": 20})

def test_duplicate_inside_window_replays_same_key():
    ud = _ud()
    key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
    ud.mark_operation_completed("TOP_UP", {"amount": 20})
    assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == key

def test_new_action_after_window_gets_fresh_key(monkeypatch):
    ud = _ud()
    key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
    ud.mark_operation_completed("TOP_UP", {"amount": 20})
    # fast-forward past the window without sleeping
    fp = ud._operation_fingerprint("TOP_UP", {"amount": 20})
    ud._completed_at[fp] = time.monotonic() - (_DUPLICATE_WINDOW_S + 1)
    assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) != key

def test_failure_keeps_key_without_window():
    ud = _ud()
    key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
    # no mark_operation_completed: a retry must reuse the key indefinitely
    assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == key

def test_distinct_payload_is_a_distinct_operation():
    ud = _ud()
    assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) != \
           ud.new_idempotency_key("TOP_UP", {"amount": 50})