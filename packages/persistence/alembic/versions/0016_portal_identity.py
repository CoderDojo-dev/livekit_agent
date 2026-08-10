"""Portal login identities (P0-1: real authentication).

Revision ID: 0016_portal_identity
Revises: 0015_outage_description_area_code
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_portal_identity"
down_revision = "0015_outage_description_area_code"
branch_labels = None
depends_on = None

_KIND_ROLE_CUSTOMER = (
    "(kind = 'staff' AND customer_id IS NULL "
    "AND role IN ('conseiller','superviseur','administrateur')) "
    "OR (kind = 'client' AND customer_id IS NOT NULL AND role = 'client')"
)


def upgrade() -> None:
    # 0009 already created this schema; the guard keeps the migration runnable standalone.
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    op.create_table(
        "portal_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "password_algo",
            sa.String(30),
            server_default=sa.text("'scrypt'"),
            nullable=False,
        ),
        sa.Column("password_params", sa.String(60), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "failed_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint("kind IN ('staff','client')", name="ck_portal_accounts_kind"),
        sa.CheckConstraint(
            "role IN ('conseiller','superviseur','administrateur','client')",
            name="ck_portal_accounts_role",
        ),
        sa.CheckConstraint(_KIND_ROLE_CUSTOMER, name="ck_portal_accounts_kind_role_customer"),
        sa.CheckConstraint(
            "failed_attempts >= 0", name="ck_portal_accounts_failed_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["crm.customers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portal_accounts"),
        sa.UniqueConstraint("email", name="uq_portal_accounts_email"),
        sa.UniqueConstraint("customer_id", name="uq_portal_accounts_customer_id"),
        schema="auth",
    )

    op.create_table(
        "portal_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(200)),
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
        sa.ForeignKeyConstraint(
            ["account_id"], ["auth.portal_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portal_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_portal_sessions_token_digest"),
        schema="auth",
    )
    op.create_index(
        "ix_portal_sessions_account_id", "portal_sessions", ["account_id"], schema="auth"
    )
    op.create_index(
        "ix_portal_sessions_expires_at", "portal_sessions", ["expires_at"], schema="auth"
    )

    op.execute(
        "CREATE TRIGGER trg_portal_accounts_updated "
        "BEFORE UPDATE ON auth.portal_accounts "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_portal_sessions_updated "
        "BEFORE UPDATE ON auth.portal_sessions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("portal_sessions", schema="auth")
    op.drop_table("portal_accounts", schema="auth")
    # The `auth` schema itself belongs to 0009. Do NOT drop it here.