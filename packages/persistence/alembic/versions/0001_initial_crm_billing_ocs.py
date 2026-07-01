"""initial: extensions, all 12 schemas, set_updated_at trigger, crm/billing/ocs tables + live view.

Subsequent slices (safety core, conversation, ...) add their tables into the schemas created here.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
import persistence.models  # noqa: F401  (registers crm/billing/ocs tables)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Every bounded-context schema exists from day one (spec section 2.1); only crm/billing/ocs
# carry tables in this slice.
SCHEMAS = [
    "crm", "billing", "ocs", "sim", "oss", "provisioning",
    "ticketing", "conversation", "policy", "execution", "audit", "reference",
]
# Mutable tables that own updated_at -> attach the trigger.
TRIGGER_TABLES = [
    ("crm", "customers"), ("crm", "subscriptions"),
    ("billing", "accounts"), ("billing", "invoices"),
    ("ocs", "balance_accounts"),
]

_SET_UPDATED_AT = (
    "CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ "
    "BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;"
)

_LIVE_VIEW = (
    "CREATE OR REPLACE VIEW crm.v_subscription_live AS "
    "SELECT s.id AS subscription_id, s.customer_id, s.msisdn, s.plan_type, s.status, "
    "b.balance_type, b.balance_value, b.balance_unit, b.expiry_date "
    "FROM crm.subscriptions s "
    "LEFT JOIN ocs.balance_accounts b ON b.subscription_id = s.id "
    "WHERE s.deleted_at IS NULL;"
)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.execute(_SET_UPDATED_AT)

    # Create crm/billing/ocs tables straight from the models (guarantees model<->DB parity).
    Base.metadata.create_all(bind=op.get_bind())

    for schema, table in TRIGGER_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )
    op.execute(_LIVE_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS crm.v_subscription_live")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")