"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import (
    audit,
    auth,
    billing,
    conversation,
    crm,
    execution,
    knowledge,
    ocs,
    oss,
    policy,
    provisioning,
    reference,
    sim,
    ticketing,
)

__all__ = [
    "audit",
    "auth",
    "billing",
    "conversation",
    "crm",
    "execution",
    "knowledge",
    "ocs",
    "oss",
    "policy",
    "provisioning",
    "reference",
    "sim",
    "ticketing",
]