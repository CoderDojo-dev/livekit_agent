"""Agent usage events (LLM metrics, v93).

Revision ID: 0018_agent_usage_events
Revises: 0017_notification_failure_reason
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0018_agent_usage_events"
down_revision = "0017_notification_failure_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_usage_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversation.call_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.String(160)),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
        sa.CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
        schema="conversation",
    )
    op.create_index(
        "ix_agent_usage_events_session_id",
        "agent_usage_events",
        ["session_id"],
        schema="conversation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_usage_events_session_id",
        table_name="agent_usage_events",
        schema="conversation",
    )
    op.drop_table("agent_usage_events", schema="conversation")
