"""Indexes for bounded AI-persona activity aggregation.

Revision ID: 0019_agent_activity_indexes
Revises: 0018_agent_usage_events
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_agent_activity_indexes"
down_revision = "0018_agent_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # Deviation (adapted to this system): migration 0018 created
        # agent_usage_events.id WITHOUT the uuid_generate_v4() default that every
        # other conversation table carries (base.UUIDPrimaryKey). Every usage
        # insert therefore failed with a NOT NULL violation and the table stayed
        # empty. The default is restored here; 0018 itself is never edited.
        op.execute(
            "ALTER TABLE conversation.agent_usage_events "
            "ALTER COLUMN id SET DEFAULT uuid_generate_v4()"
        )
        op.create_index(
            "ix_call_sessions_start_time",
            "call_sessions",
            ["start_time"],
            schema="conversation",
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_turns_active_agent_session_id",
            "turns",
            ["active_agent", "session_id"],
            schema="conversation",
            postgresql_where=sa.text(
                "active_agent IS NOT NULL AND active_agent <> ''"
            ),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_agent_usage_events_occurred_agent",
            "agent_usage_events",
            ["occurred_at", "agent"],
            schema="conversation",
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_agent_usage_events_occurred_agent",
            table_name="agent_usage_events",
            schema="conversation",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_turns_active_agent_session_id",
            table_name="turns",
            schema="conversation",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_call_sessions_start_time",
            table_name="call_sessions",
            schema="conversation",
            postgresql_concurrently=True,
        )
        op.execute(
            "ALTER TABLE conversation.agent_usage_events "
            "ALTER COLUMN id DROP DEFAULT"
        )
