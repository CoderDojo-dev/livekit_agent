from tasks.identity_verification_task import MAX_ATTEMPTS, MAX_INVALID_INPUTS


def test_invalid_budget_is_independent_from_auth_attempts() -> None:
    assert MAX_INVALID_INPUTS >= 1
    assert MAX_ATTEMPTS == 3
