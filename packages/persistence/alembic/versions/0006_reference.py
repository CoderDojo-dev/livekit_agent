"""reference catalogs: business_rules, error_catalog, products, recharge_catalog.

Revision ID: 0006_reference
Revises: 0005_ticketing_notif
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.reference import BusinessRule, ErrorCatalog, Product, RechargeCatalog

revision = "0006_reference"
down_revision = "0005_ticketing_notif"
branch_labels = None
depends_on = None

_NEW = [BusinessRule.__table__, ErrorCatalog.__table__, Product.__table__, RechargeCatalog.__table__]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    op.execute(
        "CREATE TRIGGER trg_business_rules_updated BEFORE UPDATE ON reference.business_rules "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    for table in ("business_rules", "error_catalog", "products", "recharge_catalog"):
        op.execute(f"DROP TABLE IF EXISTS reference.{table} CASCADE")
