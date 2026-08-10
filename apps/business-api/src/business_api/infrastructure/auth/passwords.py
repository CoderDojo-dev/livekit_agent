"""Password hashing for portal accounts (scrypt, standard library only).

scrypt is memory-hard and ships with CPython, so this adds no dependency to an image that
already installs ten local packages. The algorithm and its parameters are stored next to every
hash, so they can be raised later without a migration and without invalidating old rows:
verify_password() reads the parameters from the record it is checking.
"""
from __future__ import annotations

import hashlib
import hmac
import os

ALGORITHM = "scrypt"

# OWASP interactive parameters: n=2**14, r=8, p=1 -> 16 MiB, ~50-100 ms per hash.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 64
_SALT_BYTES = 16


def _maxmem(n: int, r: int, p: int) -> int:
    """OpenSSL refuses n=2**14,r=8 under its 32 MiB default; ask for exactly what we need."""
    return 128 * n * r * p * 2


def default_params() -> str:
    """Parameter string persisted in auth.portal_accounts.password_params."""
    return f"n={_N},r={_R},p={_P},dklen={_DKLEN}"


def _parse_params(params: str) -> tuple[int, int, int, int]:
    values: dict[str, int] = {}
    for item in params.split(","):
        key, _, value = item.partition("=")
        values[key.strip()] = int(value)
    return values["n"], values["r"], values["p"], values["dklen"]


def hash_password(password: str) -> tuple[str, str, str]:
    """Return ``(algorithm, params, encoded)`` for a new password.

    ``encoded`` is ``"<salt hex>$<derived hex>"`` - 32 + 1 + 128 = 161 chars, inside String(255).
    """
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=_maxmem(_N, _R, _P),
    )
    return ALGORITHM, default_params(), f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, algorithm: str, params: str, encoded: str) -> bool:
    """Constant-time verification. Returns False on any malformed record; never raises."""
    if algorithm != ALGORITHM:
        return False
    try:
        n, r, p, dklen = _parse_params(params)
        salt_hex, separator, digest_hex = encoded.partition("$")
        if not separator:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (KeyError, ValueError):
        return False
    if not salt or not expected:
        return False
    candidate = hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=_maxmem(n, r, p)
    )
    return hmac.compare_digest(candidate, expected)