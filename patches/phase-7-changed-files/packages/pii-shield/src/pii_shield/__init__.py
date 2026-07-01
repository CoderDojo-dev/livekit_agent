"""Mask PII before it crosses any cloud / log / audit boundary."""
from pii_shield.masker import PiiMasker, mask

__all__ = ["PiiMasker", "mask"]