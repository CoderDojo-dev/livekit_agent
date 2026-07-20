"""Map each customer to a GLPI user (the ticket requester).

Revision ID: 0011_customer_glpi_user
Revises: 0010_knowledge_rag
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_customer_glpi_user"
down_revision = "0010_knowledge_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("glpi_user_id", sa.Integer(), nullable=True),
        schema="crm",
    )
    op.create_unique_constraint(
        "uq_customers_glpi_user_id", "customers", ["glpi_user_id"], schema="crm"
    )
    op.create_index(
        "ix_crm_customers_glpi_user_id", "customers", ["glpi_user_id"], schema="crm"
    )


def downgrade() -> None:
    op.drop_index("ix_crm_customers_glpi_user_id", table_name="customers", schema="crm")
    op.drop_constraint("uq_customers_glpi_user_id", "customers", schema="crm", type_="unique")
    op.drop_column("customers", "glpi_user_id", schema="crm")
