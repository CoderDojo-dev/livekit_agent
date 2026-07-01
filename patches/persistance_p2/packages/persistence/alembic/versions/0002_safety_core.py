"""safety core: policy.policy_verdicts, execution.action_ledger, audit.audit_ledger + pii_token_map.

Revision ID: 0002_safety_core
Revises: 0001_initial
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.audit import AuditLedgerEntry, PiiTokenMap
from persistence.models.execution import ActionLedger
from persistence.models.policy import PolicyVerdict

revision = "0002_safety_core"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_NEW_TABLES = [PolicyVerdict.__table__, ActionLedger.__table__, AuditLedgerEntry.__table__, PiiTokenMap.__table__]


def upgrade() -> None:
    # Schemas already exist (migration 0001). Create only the safety-core tables.
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW_TABLES)
    op.execute(
        "CREATE TRIGGER trg_action_ledger_updated BEFORE UPDATE ON execution.action_ledger "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS execution.action_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS policy.policy_verdicts CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.audit_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.pii_token_map CASCADE")