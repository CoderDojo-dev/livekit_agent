"""Advisor registry for human escalation (routing schema).

Revision ID: 0012_routing_advisors
Revises: 0011_customer_glpi_user
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_routing_advisors"
down_revision = "0011_customer_glpi_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS routing")
    op.create_table(
        "advisors",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("phone_e164", sa.String(length=20)),
        sa.Column("sip_uri", sa.String(length=255)),
        sa.Column("skills", sa.String(length=200), server_default=sa.text("'general'"),
                  nullable=False),
        sa.Column("language", sa.String(length=10), server_default=sa.text("'fr'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'offline'"),
                  nullable=False),
        sa.Column("max_concurrent_calls", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("active_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_on_call", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_advisors"),
        sa.CheckConstraint("status IN ('available','busy','offline')", name="ck_advisors_status"),
        sa.CheckConstraint("max_concurrent_calls > 0", name="ck_advisors_positive_capacity"),
        sa.CheckConstraint("active_calls >= 0", name="ck_advisors_non_negative_active"),
        schema="routing",
    )
    op.create_index("ix_routing_advisors_status", "advisors", ["status"], schema="routing")
    op.create_index("ix_routing_advisors_is_on_call", "advisors", ["is_on_call"], schema="routing")


def downgrade() -> None:
    op.drop_index("ix_routing_advisors_is_on_call", table_name="advisors", schema="routing")
    op.drop_index("ix_routing_advisors_status", table_name="advisors", schema="routing")
    op.drop_table("advisors", schema="routing")