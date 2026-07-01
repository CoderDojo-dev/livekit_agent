"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import (  # noqa: F401
    audit,
    billing,
    conversation,
    crm,
    execution,
    ocs,
    policy,
)

__all__ = ["crm", "billing", "ocs", "policy", "execution", "audit", "conversation"]