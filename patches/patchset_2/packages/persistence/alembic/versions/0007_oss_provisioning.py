"""oss + provisioning tables (report #1, #2).

Revision ID: 0007_oss_provisioning
Revises: 0006_reference
Create Date: 2026-06-30
"""
from alembic import op

from persistence.base import Base
from persistence.models.oss import Alarm, NetworkElement, Outage
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder

revision = "0007_oss_provisioning"
down_revision = "0006_reference"
branch_labels = None
depends_on = None

_NEW = [
    NetworkElement.__table__, Alarm.__table__, Outage.__table__,
    ProvisioningRequest.__table__, SimOrder.__table__, PlanChangeHistory.__table__,
]
_TRIGGERS = [
    ("oss", "network_elements"), ("oss", "outages"),
    ("provisioning", "provisioning_requests"), ("provisioning", "sim_orders"),
]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    for schema, table in _TRIGGERS:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table in ("plan_change_history", "sim_orders", "provisioning_requests"):
        op.execute(f"DROP TABLE IF EXISTS provisioning.{table} CASCADE")
    for table in ("alarms", "outages", "network_elements"):
        op.execute(f"DROP TABLE IF EXISTS oss.{table} CASCADE")