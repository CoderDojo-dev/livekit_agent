from tasks.identity_verification_task import TASK_DEADLINE_S, VERIFY_CALL_TIMEOUT_S
from tools.guards import GATE_TIMEOUT_S


def test_timeouts_are_strictly_cascaded() -> None:
    """Each layer must outlive the one it wraps, or the inner failure message is cut."""
    assert VERIFY_CALL_TIMEOUT_S < TASK_DEADLINE_S < GATE_TIMEOUT_S


def test_deadline_allows_three_full_attempts() -> None:
    """3 attempts x (speech + a 5s verify call) must fit inside the watchdog."""
    assert TASK_DEADLINE_S >= 3 * (VERIFY_CALL_TIMEOUT_S + 8.0)
