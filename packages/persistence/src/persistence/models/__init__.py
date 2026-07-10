"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import (
    auth,
    audit,
    billing,
    conversation,
    crm,
    execution,
    ocs,
    oss,
    policy,
    provisioning,
    reference,
    sim,
    ticketing,
)

__all__ = [
    "auth",
    "audit",
    "billing",
    "conversation",
    "crm",
    "execution",
    "ocs",
    "oss",
    "policy",
    "provisioning",
    "reference",
    "sim",
    "ticketing",
]