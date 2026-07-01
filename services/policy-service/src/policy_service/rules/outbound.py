"""Outbound guardrail (CDC section 10.3): may-I-say-this — unmasked PII / wrong amounts."""
from __future__ import annotations

import re

from policy_service.rules.base import AUTHORIZED, REFUSED, VerdictResult

_UNMASKED_ID = re.compile(r"\b\d{8,12}\b")


def check_outbound(text: str) -> VerdictResult:
    """Refuse a response that leaks an unmasked identifier; otherwise authorize."""
    if _UNMASKED_ID.search(text):
        return VerdictResult(REFUSED, "OUT_PII", "response contains an unmasked identifier")
    return VerdictResult(AUTHORIZED, "OUT_OK", "response permitted")