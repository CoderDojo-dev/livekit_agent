"""Motif d'echec de notification (R8).

Revision ID: 0017_notification_failure_reason
Revises: 0016_portal_identity
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_notification_failure_reason"
down_revision = "0016_portal_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications", sa.Column("failure_reason", sa.String(200)), schema="billing"
    )
    op.create_check_constraint(
        "failure_reason_only_when_failed",
        "notifications",
        "failure_reason IS NULL OR status = 'failed'",
        schema="billing",
    )


def downgrade() -> None:
    op.drop_constraint(
        "failure_reason_only_when_failed",
        "notifications",
        schema="billing",
        type_="check",
    )
    op.drop_column("notifications", "failure_reason", schema="billing")