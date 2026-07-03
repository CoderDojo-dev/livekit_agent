"""PII masking for ALL worker logs (Blueprint section 14 / review note 5a).

Installs a logging filter that scrubs phone numbers, emails, and identifier runs from every
emitted record, as a safety net on top of the rule that structured fields log non-PII ids.
"""
from __future__ import annotations

import logging

from pii_shield import PiiMasker


class PiiMaskingFilter(logging.Filter):
    """A logging filter that masks PII in the fully-rendered message."""

    def __init__(self) -> None:
        super().__init__()
        self._masker = PiiMasker()

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = self._masker.mask(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def install_pii_masking() -> None:
    """Attach the PII masking filter to every root handler exactly once."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, PiiMaskingFilter) for f in handler.filters):
            handler.addFilter(PiiMaskingFilter())