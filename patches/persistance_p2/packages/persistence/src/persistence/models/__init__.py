"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import audit, billing, crm, execution, ocs, policy  # noqa: F401

__all__ = ["crm", "billing", "ocs", "policy", "execution", "audit"]