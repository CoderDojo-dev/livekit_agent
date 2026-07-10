"""Customer-bound CIN verification persistence.

Revision ID: 0009_auth_identity
Revises: 0008_gin_indexes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_auth_identity"
down_revision = "0008_gin_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    op.create_table(
        "customer_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "verifier_type",
            sa.String(30),
            server_default=sa.text("'cin_last4'"),
            nullable=False,
        ),
        sa.Column(
            "verifier_digest",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "key_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verifier_type IN ('cin_last4')",
            name="ck_customer_credentials_verifier_type",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["crm.customers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_customer_credentials",
        ),
        sa.UniqueConstraint(
            "customer_id",
            "verifier_type",
            name="uq_customer_credentials_customer_type",
        ),
        schema="auth",
    )
    op.create_index(
        "ix_customer_credentials_customer_id",
        "customer_credentials",
        ["customer_id"],
        schema="auth",
    )

    op.create_table(
        "verification_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "call_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.String(30),
            server_default=sa.text("'cin_last4'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('cin_last4')",
            name="ck_verification_sessions_method",
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending','verified','failed','locked','expired')",
            name="ck_verification_sessions_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 "
            "AND attempt_count <= max_attempts",
            name="ck_verification_sessions_attempt_bounds",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["crm.customers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_verification_sessions",
        ),
        schema="auth",
    )
    op.create_index(
        "ix_verification_sessions_call_session_id",
        "verification_sessions",
        ["call_session_id"],
        schema="auth",
    )
    op.create_index(
        "ix_verification_sessions_customer_status",
        "verification_sessions",
        ["customer_id", "status"],
        schema="auth",
    )

    op.create_table(
        "verification_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "verification_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(120)),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('started','attempt_succeeded','attempt_failed',"
            "'locked','expired')",
            name="ck_verification_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["verification_session_id"],
            ["auth.verification_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_verification_events",
        ),
        schema="auth",
    )
    op.create_index(
        "ix_verification_events_verification_session_id",
        "verification_events",
        ["verification_session_id"],
        schema="auth",
    )

    op.execute(
        "CREATE TRIGGER trg_customer_credentials_updated "
        "BEFORE UPDATE ON auth.customer_credentials "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_verification_sessions_updated "
        "BEFORE UPDATE ON auth.verification_sessions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table(
        "verification_events",
        schema="auth",
    )
    op.drop_table(
        "verification_sessions",
        schema="auth",
    )
    op.drop_table(
        "customer_credentials",
        schema="auth",
    )
    op.execute("DROP SCHEMA IF EXISTS auth")
