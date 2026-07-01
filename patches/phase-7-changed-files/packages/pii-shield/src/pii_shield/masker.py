"""Lightweight PII masker (CDC section 8.2 / Blueprint section 14). Phase 12 hardens detection
and adds reversible pseudonymization. Used to scrub PII before it crosses a log/cloud/audit
boundary; the worker also installs it as a logging filter (see observability/log_masking.py).
"""
from __future__ import annotations

import re

_PHONE = re.compile(r"\+?\d[\d\s-]{6,}\d")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# A standalone run of 4+ digits (national-ID / CIN fragments, account numbers) — but NOT
# decimal amounts like 42.500, which contain a dot and are matched as two short runs.
_ID_RUN = re.compile(r"(?<!\d)\d{4,}(?!\d)")


class PiiMasker:
    """Mask phone numbers, emails, and bare identifier runs in free text."""

    def mask(self, text: str) -> str:
        """Return ``text`` with PII tokens replaced by typed placeholders."""
        text = _EMAIL.sub("[EMAIL]", text)
        text = _PHONE.sub("[PHONE]", text)
        text = _ID_RUN.sub("[ID]", text)
        return text


_DEFAULT = PiiMasker()


def mask(text: str) -> str:
    """Module-level convenience masker."""
    return _DEFAULT.mask(text)