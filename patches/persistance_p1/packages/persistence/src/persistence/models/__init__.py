"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import billing, crm, ocs  # noqa: F401

__all__ = ["crm", "billing", "ocs"]