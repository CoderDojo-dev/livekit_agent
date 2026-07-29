"""Outbound guardrail (CDC section 10.3): may-I-say-this — typed PII patterns only."""
from __future__ import annotations

import re

from policy_service.rules.base import AUTHORIZED, REFUSED, VerdictResult

# 9-12 consecutive digits NOT preceded by a currency marker (TND / DT) or 'X' (already masked).
_CUSTOMER_ID = re.compile(r"(?<![TtNnDdXx])\b\d{9,12}\b")
# Tunisian mobile numbers starting with 2, 5, or 9 (8 digits after the prefix).
_MOBILE = re.compile(r"\b[259]\d{7}\b")
# Credit-card-like patterns: 4 groups of 4 digits separated by spaces.
_CREDIT_CARD = re.compile(r"\b\d{4} \d{4} \d{4} \d{4}\b")

_PII_PATTERNS = (_CUSTOMER_ID, _MOBILE, _CREDIT_CARD)


def check_outbound(text: str) -> VerdictResult:
    """Refuse a response that leaks typed PII; otherwise authorize."""
    for pattern in _PII_PATTERNS:
        if pattern.search(text):
            return VerdictResult(REFUSED, "OUT_PII", "response contains an unmasked identifier")
    return VerdictResult(AUTHORIZED, "OUT_OK", "response permitted")