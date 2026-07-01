"""Shared resilience helper: the chaos toggle used by each provider builder (cookbook section 16).

Keeping the swap in one tiny module means the three builders apply it identically and there
is a single definition of the deliberately invalid model id.
"""
from __future__ import annotations

# A deliberately invalid model id used to force a primary failure in chaos runs.
INVALID_MODEL = "chaos-invalid-model-does-not-exist"


def chaos_model(real_model: str, break_primary: bool) -> str:
    """Return ``real_model``, or the invalid id when ``break_primary`` is set."""
    return INVALID_MODEL if break_primary else real_model