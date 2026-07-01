"""GIN indexes on JSONB columns for @> / ? queries (report #14).

Revision ID: 0008_gin_indexes
Revises: 0007_oss_provisioning
Create Date: 2026-06-30
"""
from alembic import op

revision = "0008_gin_indexes"
down_revision = "0007_oss_provisioning"
branch_labels = None
depends_on = None

# (index_name, schema, table, column)
_GIN = [
    ("ix_policy_verdicts_inputs_gin", "policy", "policy_verdicts", "inputs_snapshot"),
    ("ix_action_ledger_parameters_gin", "execution", "action_ledger", "parameters"),
    ("ix_escalation_cases_dossier_gin", "conversation", "escalation_cases", "dossier"),
    ("ix_audit_ledger_payload_gin", "audit", "audit_ledger", "payload"),
    ("ix_business_rules_definition_gin", "reference", "business_rules", "definition_json"),
    ("ix_provisioning_requests_parameters_gin", "provisioning", "provisioning_requests", "parameters"),
]


def upgrade() -> None:
    for name, schema, table, column in _GIN:
        op.create_index(name, table, [column], schema=schema, postgresql_using="gin")


def downgrade() -> None:
    for name, schema, _table, _column in _GIN:
        op.drop_index(name, schema=schema)