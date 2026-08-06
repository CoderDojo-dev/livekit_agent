"""Contract tests for the notification send log (FEATURE_18).

Neither test inserts a row. billing.notifications has no NOT NULL column the tests could
violate, but crm.customers.national_id is nullable=False and cookbooks forbid setting it, so
the FEATURE_16 lesson stands: assert on shape and clamping, never on seeded content.
"""
from business_api.repositories import SupervisionRepository


def test_notification_list_shape_and_clamps(db_session):
    """The five documented keys are always present, and limit/offset are clamped, not trusted."""
    result = SupervisionRepository(db_session).notification_list(limit=0, offset=-5)

    assert set(result) == {"notifications", "total", "counts", "limit", "offset"}
    assert result["limit"] == 1
    assert result["offset"] == 0
    assert isinstance(result["notifications"], list)
    assert isinstance(result["counts"], dict)
    assert isinstance(result["total"], int)


def test_notification_list_unknown_channel_returns_nothing(db_session):
    """An out-of-enum channel filters everything out rather than being ignored."""
    result = SupervisionRepository(db_session).notification_list(channel="carrier-pigeon")

    assert result["notifications"] == []
    assert result["total"] == 0