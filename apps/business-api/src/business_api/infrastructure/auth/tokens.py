"""Opaque session tokens.

The token is returned to the caller once and never stored: auth.portal_sessions keeps only its
SHA-256 digest, exactly like a password-reset token. A dump of the database therefore cannot be
replayed against the API.

SHA-256 without a salt is correct here and NOT a weak password hash: the input is 256 bits of
cryptographic randomness, so there is nothing to brute-force or rainbow-table.
"""
from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    """A fresh URL-safe opaque token carrying 256 bits of entropy."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    """SHA-256 hex digest stored in auth.portal_sessions.token_digest (64 chars)."""
    return hashlib.sha256(token.encode()).hexdigest()