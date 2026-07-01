"""Small persistence helpers."""
from __future__ import annotations

import uuid

_NS = uuid.UUID("00000000-0000-0000-0000-0000000000aa")  # stable namespace for non-UUID ids


def to_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Parse ``value`` as a UUID, or None for empty input."""
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def require_uuid(value: str | uuid.UUID | None) -> uuid.UUID:
    """Coerce ``value`` to a UUID, deriving a stable one for non-UUID strings (e.g. 'unknown')."""
    parsed = to_uuid(value)
    return parsed if parsed is not None else uuid.uuid5(_NS, str(value))