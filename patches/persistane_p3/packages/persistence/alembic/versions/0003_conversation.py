"""conversation runtime: call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules.

Revision ID: 0003_conversation
Revises: 0002_safety_core
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.conversation import (
    CallbackSchedule,
    CallSession,
    EscalationCase,
    SentimentSample,
    Turn,
)

revision = "0003_conversation"
down_revision = "0002_safety_core"
branch_labels = None
depends_on = None

_NEW = [
    CallSession.__table__, Turn.__table__, SentimentSample.__table__,
    EscalationCase.__table__, CallbackSchedule.__table__,
]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    op.execute(
        "CREATE TRIGGER trg_callback_schedules_updated BEFORE UPDATE ON conversation.callback_schedules "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    for table in ("callback_schedules", "escalation_cases", "sentiment_samples", "turns", "call_sessions"):
        op.execute(f"DROP TABLE IF EXISTS conversation.{table} CASCADE")