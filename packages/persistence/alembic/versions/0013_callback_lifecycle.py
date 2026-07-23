"""Callback queue lifecycle: assignment, outcome, and the caller's own words.

Revision ID: 0013_callback_lifecycle
Revises: 0012_routing_advisors
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_callback_lifecycle"
down_revision = "0012_routing_advisors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("callback_schedules",
                  sa.Column("assigned_advisor_id", sa.UUID(as_uuid=True)), schema="conversation")
    op.create_foreign_key("fk_callbacks_advisor", "callback_schedules", "advisors",
                          ["assigned_advisor_id"], ["id"],
                          source_schema="conversation", referent_schema="routing",
                          ondelete="SET NULL")
    # What the caller actually said ("demain matin"), kept verbatim so the advisor sees the real
    # request even when it could not be parsed into a timestamp.
    op.add_column("callback_schedules",
                  sa.Column("preferred_window", sa.String(length=120)), schema="conversation")
    op.add_column("callback_schedules",
                  sa.Column("reason", sa.String(length=60)), schema="conversation")
    op.add_column("callback_schedules",
                  sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
                  schema="conversation")
    op.add_column("callback_schedules",
                  sa.Column("outcome_note", sa.String(length=500)), schema="conversation")
    op.add_column("callback_schedules",
                  sa.Column("completed_at", sa.DateTime(timezone=True)), schema="conversation")
    op.create_index("ix_conversation_callbacks_status_time", "callback_schedules",
                    ["status", "scheduled_time"], schema="conversation")


def downgrade() -> None:
    op.drop_index("ix_conversation_callbacks_status_time", table_name="callback_schedules",
                  schema="conversation")
    for column in ("completed_at", "outcome_note", "attempts", "reason", "preferred_window"):
        op.drop_column("callback_schedules", column, schema="conversation")
    op.drop_constraint("fk_callbacks_advisor", "callback_schedules",
                       schema="conversation", type_="foreignkey")
    op.drop_column("callback_schedules", "assigned_advisor_id", schema="conversation")
