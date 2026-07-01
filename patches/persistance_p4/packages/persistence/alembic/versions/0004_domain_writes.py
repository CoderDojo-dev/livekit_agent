"""domain write projections: billing.payments/payment_plans, ocs.recharges, sim.block_unblock_cases.

Revision ID: 0004_domain_writes
Revises: 0003_conversation
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.billing import Payment, PaymentPlan
from persistence.models.ocs import Recharge
from persistence.models.sim import BlockUnblockCase

revision = "0004_domain_writes"
down_revision = "0003_conversation"
branch_labels = None
depends_on = None

_NEW = [Payment.__table__, PaymentPlan.__table__, Recharge.__table__, BlockUnblockCase.__table__]
_TRIGGERS = [("billing", "payments"), ("billing", "payment_plans"), ("sim", "block_unblock_cases")]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    for schema, table in _TRIGGERS:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing.payments CASCADE")
    op.execute("DROP TABLE IF EXISTS billing.payment_plans CASCADE")
    op.execute("DROP TABLE IF EXISTS ocs.recharges CASCADE")
    op.execute("DROP TABLE IF EXISTS sim.block_unblock_cases CASCADE")
