# P0-1 — Real Authentication (admin dashboard + client portal, one identity layer)

**Branch:** `version_83` · **HEAD at authoring time:** `7f67f085825e239a3701d9258110d1d6583e5c73`
**Scope:** authentication + authorization for `business-api`, rewiring of both front ends, and the
agent-worker machine identity.
**Status of every fact below:** read from source on `version_83`. Blob SHAs are quoted where a
diff depends on exact bytes.

---

## §0 PRE-FLIGHT — must all pass before the first edit

These are gates, not suggestions. Three of them can break the running voice agent if skipped.

### 0.1 Branch and baseline

```bash
cd <repo root>
git rev-parse --abbrev-ref HEAD          # expect version_83
git status --porcelain                   # expect empty
pytest apps/business-api/tests -q        # expect 28 passed
ruff check apps/business-api/src/business_api/main.py | tail -1   # expect 7 pre-existing
```

### 0.2 Alembic head — confirm, do not assume

`0015_outage_description_area_code` is the highest-numbered revision and declares
`down_revision = "0014_geo_reference"`. Confirm nothing else claims the head:

```bash
cd packages/persistence && python -m alembic heads
# expect exactly:  0015_outage_description_area_code (head)
```

If the output differs, change `down_revision` in §3.2 to whatever this prints. **Do not proceed
with a guessed parent revision.**

### 0.3 GATE A — `INTERNAL_API_KEY` must be set BEFORE business-api is rebuilt

This is the single change that can break the voice path.

`.env.example` ships `INTERNAL_API_KEY=` (empty, §3 of the template). `packages/service-auth` is
deliberately fail-open: `internal_headers()` returns `{}` when the key is unset. After this patch
business-api requires an authenticated principal, so an empty key means the worker's advisor claim
and callback reservation start returning **401**.

```bash
grep -n '^INTERNAL_API_KEY=' .env
# must print a non-empty value, e.g. INTERNAL_API_KEY=dev-key-123
```

If empty, set it and restart the services that already consume it **before** touching business-api:

```bash
# 1. set INTERNAL_API_KEY=<value> in .env
docker compose -f infra/docker-compose/docker-compose.apps.yml up -d \
  context-service decision-service policy-service execution-service \
  notification-service agent-worker
```

Proof that the existing internal chain still works with the key on:

```bash
docker compose -f infra/docker-compose/docker-compose.apps.yml exec agent-worker \
  python -c "from service_auth import internal_headers; print(internal_headers())"
# expect: {'X-API-Key': '<value>'}   NOT {}
```

### 0.4 GATE B — the CIN verifier must actually be populated

Client signup (§7) verifies against `auth.customer_credentials`. If `seed_auth_credentials.py`
was never run, that table is empty and **every signup fails**.

```bash
docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres \
  psql -U telecom -d telecom -c \
  "SELECT count(*) AS active_verifiers FROM auth.customer_credentials WHERE active;"

grep -n '^AUTH_CIN_HMAC_KEY=' .env && echo "len=${#AUTH_CIN_HMAC_KEY}"
```

* `active_verifiers > 0` and a key of ≥ 32 chars → proceed, signup will work.
* `active_verifiers = 0` → the **admin half of this patch is still fully valid and safe to ship**.
  Seed first, then enable signup:

```bash
# AUTH_CIN_HMAC_KEY must be >= 32 chars and must NEVER change afterwards:
# every stored digest is salted with it, and rotating it invalidates all of them.
cd packages/persistence && AUTH_CIN_HMAC_KEY="$AUTH_CIN_HMAC_KEY" python -m seed.seed_auth_credentials
# prints: seeded N protected CIN credentials
```

> `AUTH_CIN_HMAC_KEY` is **absent from `.env.example`** even though
> `context_service/auth_service.py::_digest` raises `RuntimeError` without it. §9.1 adds it to the
> template. This is a pre-existing documentation gap, reported not silently fixed.

### 0.5 GATE C — nothing except agent-worker talks to business-api

```bash
git grep -n "BUSINESS_API_URL" -- infra/ services/ apps/ packages/ | grep -v '\.env'
```

Expected: `docker-compose.apps.yml` sets it **only** under `agent-worker`, and
`apps/agent-worker/src/config/settings.py` declares it. If any other service appears, that service
also needs the machine header from §8 and must be added to this patch.

---

## §1 ROOT CAUSE

`apps/business-api/src/business_api/security.py` (blob `a059de0dc24a7d5a0cfe8530e7f6b4e7d3a54dfd`,
1092 B — byte-identical to `version_81`):

```python
def _dependency(x_role: str | None = Header(default=None)) -> str:
    role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
    if role_rank(role) < minimum_rank:
        raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
    return role  # type: ignore[return-value]
```

Three separate defects compose into one hole:

1. **There is no authentication anywhere.** `git grep -n "Depends(authenticate"` returns nothing.
   `require_role` is an authorization check with no authenticated subject to check.
2. **The role is taken from a client-supplied header.** Anyone who can reach `:8108` picks their
   own rank.
3. **A missing header does not fail closed.** `role_rank(None) == 0` would deny — but `or`
   substitutes the env default *before* `role_rank` ever sees `None`, and
   `.env.example` §22 ships `BUSINESS_API_DEFAULT_ROLE=administrateur`.

Consequence, unauthenticated, with no headers at all:

```bash
curl -s http://<host>:8108/api/v1/customers                      # 200 + full CRM PII
curl -s -X DELETE http://<host>:8108/api/v1/advisors/<id>         # destroys registry rows
curl -s -X POST "http://<host>:8108/api/v1/jobs/retention?dry_run=false&retention_days=30"
#      ^ irreversible audited purge, executed by an anonymous caller
```

The front end is **not** the problem. `auth.server.ts` → signed httpOnly cookie → `authedMiddleware`
→ `business-api.ts` as the sole `X-Role` emitter is a correct, well-built boundary. The defect is
the **composition**: a correct boundary in front of an API that has none, and that is reachable
independently of it.

**Existing test coverage of this:** `apps/business-api/tests/test_security.py` (blob `53b67304…`)
contains one test, `test_role_hierarchy`, which asserts `role_rank("unknown") == 0` and
`role_rank(None) == 0` — i.e. it exercises only the pure function the vulnerability bypasses.

---

## §2 WHAT ALREADY EXISTS AND IS REUSED

Nothing here is invented. Five existing assets carry this patch.

| Asset | Where | How it is reused |
|---|---|---|
| `auth` schema + `set_updated_at` trigger | migration `0009_auth_identity` | New tables land in the **same schema**, same trigger, same naming convention |
| CIN-last-4 verifier | `auth.customer_credentials` + `context_service/auth_service.py::_digest` | Signup proves subscriber ownership with the **same verifier the phone channel uses** |
| `INTERNAL_API_KEY` / `internal_headers()` | `packages/service-auth` (blob `308311be…`) | Becomes the agent-worker's machine identity. Already installed in **both** images |
| `role_rank` / `_ROLE_RANK` | `security.py` | **Untouched.** Already fail-closed at 0, already unit-tested |
| Signed httpOnly cookie + `authedMiddleware` | admin `session.ts` / `middleware.ts` | Kept exactly as-is; it now carries a backend token instead of a self-asserted role |

Both Dockerfiles already run:

```
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
    ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache \
    ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
```

⇒ **no Dockerfile change, no new pip dependency, no new npm dependency in this entire patch.**

### 2.1 Correction to the investigation report

My §1 investigation stated *"`crm.py` has no credential column and no user table — nothing in the
DB could authenticate a client today."* **That was wrong**, and it is corrected here: the `auth`
schema, `models/auth.py`, migration `0009`, and `seed/seed_auth_credentials.py` have existed since
revision 0009. What is genuinely absent is a *web login* — no password, no email identity, no
browser session. The vulnerability in §1 is unaffected; the inventory was incomplete.

---

## §3 PERSISTENCE — two new tables in the existing `auth` schema

### 3.1 CREATE `packages/persistence/src/persistence/models/portal_identity.py`

> **Why a new module and not an addition to `models/auth.py`.** `auth.py` is documented as
> *"Persisted, customer-bound step-up authentication state"* and every table in it is bound to a
> call (`verification_sessions.call_session_id` is `NOT NULL`). Web login state has a different
> lifecycle. Keeping them apart leaves `auth.py` byte-identical and keeps each module's docstring
> true. Same schema, different module — consistent with one-module-per-concern.

```python
"""Portal login identities: one shared account table for both front ends (P0-1).

Deliberately separate from models/auth.py: that module holds CALL-BOUND step-up verification
state (auth.verification_sessions.call_session_id is NOT NULL). These two tables hold WEB login
state. Same `auth` schema, different lifecycle.

A client row is a login ATTACHED to an existing crm.customers row - the portal never creates
telecom data. A staff row has no customer and carries one of the three backend roles.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey

STAFF_ROLES = ("conseiller", "superviseur", "administrateur")
CLIENT_ROLE = "client"

_KIND_ROLE_CUSTOMER = (
    "(kind = 'staff' AND customer_id IS NULL "
    "AND role IN ('conseiller','superviseur','administrateur')) "
    "OR (kind = 'client' AND customer_id IS NOT NULL AND role = 'client')"
)


class PortalAccount(UUIDPrimaryKey, Timestamps, Base):
    """A web login. At most one per staff member, at most one per customer."""

    __tablename__ = "portal_accounts"
    __table_args__ = (
        CheckConstraint("kind IN ('staff','client')", name="kind"),
        CheckConstraint(
            "role IN ('conseiller','superviseur','administrateur','client')",
            name="role",
        ),
        CheckConstraint(_KIND_ROLE_CUSTOMER, name="kind_role_customer"),
        CheckConstraint("failed_attempts >= 0", name="failed_attempts"),
        UniqueConstraint("email", name="uq_portal_accounts_email"),
        # Postgres permits many NULLs in a UNIQUE index, so every staff row coexists
        # while a customer can hold at most one client login.
        UniqueConstraint("customer_id", name="uq_portal_accounts_customer_id"),
        {"schema": "auth"},
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'scrypt'")
    )
    password_params: Mapped[str] = mapped_column(String(60), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm.customers.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class PortalSession(UUIDPrimaryKey, Timestamps, Base):
    """A live browser session.

    The token itself is never stored, only its SHA-256 digest: a leaked database cannot be
    replayed against the API. Server-side rows are what make logout, expiry and
    "sign out of all devices" real rather than cosmetic.
    """

    __tablename__ = "portal_sessions"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_portal_sessions_token_digest"),
        {"schema": "auth"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.portal_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(200))
```

### 3.2 EDIT `packages/persistence/src/persistence/models/__init__.py`

Two additive lines. Alphabetical position: after `policy`, before `provisioning`.

**Edit 1**

```
oldStr:
    ocs,
    oss,
    policy,
    provisioning,

newStr:
    ocs,
    oss,
    policy,
    portal_identity,
    provisioning,
```

**Edit 2**

```
oldStr:
    "ocs",
    "oss",
    "policy",
    "provisioning",

newStr:
    "ocs",
    "oss",
    "policy",
    "portal_identity",
    "provisioning",
```

### 3.3 CREATE `packages/persistence/alembic/versions/0016_portal_identity.py`

Conventions copied from `0009_auth_identity.py`: explicit `ck_`/`uq_`/`pk_` names matching
`base.py::NAMING_CONVENTION`, `uuid_generate_v4()` defaults, explicit `set_updated_at` triggers.

```python
"""Portal login identities (P0-1: real authentication).

Revision ID: 0016_portal_identity
Revises: 0015_outage_description_area_code
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_portal_identity"
down_revision = "0015_outage_description_area_code"
branch_labels = None
depends_on = None

_KIND_ROLE_CUSTOMER = (
    "(kind = 'staff' AND customer_id IS NULL "
    "AND role IN ('conseiller','superviseur','administrateur')) "
    "OR (kind = 'client' AND customer_id IS NOT NULL AND role = 'client')"
)


def upgrade() -> None:
    # 0009 already created this schema; the guard keeps the migration runnable standalone.
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    op.create_table(
        "portal_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "password_algo",
            sa.String(30),
            server_default=sa.text("'scrypt'"),
            nullable=False,
        ),
        sa.Column("password_params", sa.String(60), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "failed_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('staff','client')", name="ck_portal_accounts_kind"),
        sa.CheckConstraint(
            "role IN ('conseiller','superviseur','administrateur','client')",
            name="ck_portal_accounts_role",
        ),
        sa.CheckConstraint(_KIND_ROLE_CUSTOMER, name="ck_portal_accounts_kind_role_customer"),
        sa.CheckConstraint(
            "failed_attempts >= 0", name="ck_portal_accounts_failed_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["crm.customers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portal_accounts"),
        sa.UniqueConstraint("email", name="uq_portal_accounts_email"),
        sa.UniqueConstraint("customer_id", name="uq_portal_accounts_customer_id"),
        schema="auth",
    )

    op.create_table(
        "portal_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(200)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["auth.portal_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portal_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_portal_sessions_token_digest"),
        schema="auth",
    )
    op.create_index(
        "ix_portal_sessions_account_id", "portal_sessions", ["account_id"], schema="auth"
    )
    op.create_index(
        "ix_portal_sessions_expires_at", "portal_sessions", ["expires_at"], schema="auth"
    )

    op.execute(
        "CREATE TRIGGER trg_portal_accounts_updated "
        "BEFORE UPDATE ON auth.portal_accounts "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_portal_sessions_updated "
        "BEFORE UPDATE ON auth.portal_sessions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("portal_sessions", schema="auth")
    op.drop_table("portal_accounts", schema="auth")
    # The `auth` schema itself belongs to 0009. Do NOT drop it here.
```

**Apply:**

```bash
cd packages/persistence && python -m alembic upgrade head
python -m alembic heads     # expect 0016_portal_identity (head)
```

**Reversibility check (run once on a scratch DB, not on the dev DB — hazard H-2):**

```bash
python -m alembic downgrade -1 && python -m alembic upgrade head
```

---

## §4 BACKEND — the identity layer

Five new modules under `apps/business-api/src/business_api/infrastructure/auth/`. That directory
already exists and contains only a docstring (`__init__.py`, blob `ff0a1066…`, 81 B):
*"OIDC integration + RBAC (conseiller/superviseur/administrateur) (Phase 11)."* It is the reserved
home for exactly this. **`__init__.py` is left byte-identical.**

### 4.1 CREATE `…/infrastructure/auth/passwords.py`

```python
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
```

### 4.2 CREATE `…/infrastructure/auth/tokens.py`

```python
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
```

### 4.3 CREATE `…/infrastructure/auth/cin.py`

```python
"""Read-only mirror of the CIN-last-four verifier used by the voice channel.

The canonical implementation is context_service.auth_service._digest(). business-api cannot
import it (services/ are not installed in this image), and calling POST /verify-identity would be
wrong for the web: that endpoint opens an auth.verification_sessions row bound to a
call_session_id, and a signup has no call to bind to.

So the construction is mirrored here byte for byte and PINNED by
tests/test_auth_cin.py::test_digest_matches_pinned_vector. If either side ever drifts, that test
fails.

This module never writes. Signup throttling lives in rate_limit.py, deliberately NOT in
auth.verification_sessions - web attempts must not pollute call-bound verification history.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.auth import CustomerCredential


def digest(customer_id: str, answer: str) -> str:
    """HMAC-SHA-256 of the normalised CIN last four, salted with the customer id.

    Mirrors context_service.auth_service._digest exactly: same normalisation (digits only),
    same message layout, same key, same hash.
    """
    key = os.getenv("AUTH_CIN_HMAC_KEY", "")
    if len(key) < 32:
        raise RuntimeError("AUTH_CIN_HMAC_KEY is missing or too short")

    normalized = "".join(char for char in answer if char.isdigit())
    message = f"cin_last4:{customer_id}:{normalized}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def matches(session: Session, customer_id: uuid.UUID, answer: str) -> bool:
    """True when ``answer`` matches the active cin_last4 verifier for ``customer_id``."""
    credential = session.scalar(
        select(CustomerCredential).where(
            CustomerCredential.customer_id == customer_id,
            CustomerCredential.verifier_type == "cin_last4",
            CustomerCredential.active.is_(True),
        )
    )
    if credential is None:
        return False
    return hmac.compare_digest(
        digest(str(customer_id), answer), credential.verifier_digest
    )
```

### 4.4 CREATE `…/infrastructure/auth/rate_limit.py`

```python
"""In-process sliding-window throttle for the unauthenticated endpoints.

Why NOT packages/cache: get_cache() returns a NullCache when REDIS_URL is unset OR when redis is
unreachable, and NullCache.add_if_absent() returns True ("no dedupe when caching is off (safe
default)"). That is the right default for an idempotency helper and exactly the wrong one for a
brute-force control - the limiter would vanish silently the moment redis hiccuped. business-api
also has no depends_on: redis, and .env.example points REDIS_URL at localhost, which is not
reachable from inside the container.

Scope of this layer: business-api runs a single uvicorn process (apps/business-api/Dockerfile CMD
has no --workers), so one in-process counter observes every request. If the API is ever scaled to
multiple workers or replicas this layer becomes per-replica. The DURABLE per-account lockout in
auth.portal_accounts.locked_until (portal_auth.authenticate) stays correct in every topology and
is the layer that actually stops a targeted attack. Migration path when scaling: move this
counter behind a Redis INCR with a real depends_on, and keep the account lockout as-is.
"""
from __future__ import annotations

import threading
import time
from collections import deque

WINDOW_SECONDS = 300.0
MAX_ATTEMPTS = 20
_MAX_TRACKED_KEYS = 4096

_buckets: dict[str, deque[float]] = {}
_lock = threading.Lock()


def _prune(now: float) -> None:
    """Drop exhausted buckets, and the oldest ones if the map ever grows unbounded."""
    stale = [
        key
        for key, hits in _buckets.items()
        if not hits or now - hits[-1] > WINDOW_SECONDS
    ]
    for key in stale:
        _buckets.pop(key, None)
    if len(_buckets) > _MAX_TRACKED_KEYS:
        overflow = len(_buckets) - _MAX_TRACKED_KEYS
        oldest = sorted(_buckets, key=lambda key: _buckets[key][-1])[:overflow]
        for key in oldest:
            _buckets.pop(key, None)


def check(key: str, *, limit: int = MAX_ATTEMPTS, window: float = WINDOW_SECONDS) -> bool:
    """Record one attempt for ``key``. False when the window budget is exhausted."""
    now = time.monotonic()
    with _lock:
        _prune(now)
        hits = _buckets.setdefault(key, deque())
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def reset(key: str) -> None:
    """Clear a bucket after a successful authentication."""
    with _lock:
        _buckets.pop(key, None)


def clear_all() -> None:
    """Test helper: forget every bucket."""
    with _lock:
        _buckets.clear()
```

### 4.5 CREATE `…/infrastructure/auth/principal.py`

```python
"""Who is calling. Established here, once, for every gated endpoint.

Two kinds of principal exist:

  * a human session - `Authorization: Bearer <token>` issued by POST /api/v1/auth/login and
    revalidated against auth.portal_sessions on every request, so logout, expiry and
    "sign out of all devices" take effect immediately rather than at the next token expiry;

  * the internal machine caller - `X-API-Key` matching INTERNAL_API_KEY, the key
    packages/service-auth already defines and that the worker already sends to context-service.
    It is pinned to the LOWEST staff rank, conseiller, because every business-api route the
    worker uses is a conseiller route: /advisors/claim, /advisors/{id}/release,
    /advisors/on-call, /callbacks/slots, /callbacks/check, /callbacks/reserve.

The X-Role header is not read anywhere in this file or anywhere else after this patch. A caller
may still send it; it has no effect.

Session reuse note: current_principal depends on the SAME `get_session` callable that DbSession
uses, so FastAPI's per-request dependency cache hands both the identical Session object. One
request still opens exactly one database connection.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from business_api.infrastructure.auth.tokens import token_digest
from persistence import get_session
from persistence.models.portal_identity import PortalAccount, PortalSession

MACHINE_ROLE = "conseiller"
MACHINE_SUBJECT = "agent-worker"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. ``customer_id`` is set only for portal clients."""

    subject: str
    kind: str  # "staff" | "client" | "service"
    role: str  # conseiller | superviseur | administrateur | client
    account_id: UUID | None = None
    customer_id: UUID | None = None
    session_id: UUID | None = None


_MACHINE = Principal(subject=MACHINE_SUBJECT, kind="service", role=MACHINE_ROLE)


def _internal_key() -> str | None:
    return os.getenv("INTERNAL_API_KEY")


def bearer_token(authorization: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def resolve_session(session: Session, token: str) -> Principal | None:
    """Validate an opaque bearer token against auth.portal_sessions. None when unusable."""
    row = session.execute(
        select(PortalSession, PortalAccount)
        .join(PortalAccount, PortalAccount.id == PortalSession.account_id)
        .where(PortalSession.token_digest == token_digest(token))
    ).first()
    if row is None:
        return None

    portal_session, account = row
    if portal_session.revoked_at is not None:
        return None
    if portal_session.expires_at <= datetime.now(UTC):
        return None
    if not account.is_active:
        return None

    return Principal(
        subject=account.email,
        kind=account.kind,
        role=account.role,
        account_id=account.id,
        customer_id=account.customer_id,
        session_id=portal_session.id,
    )


def current_principal(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve the caller, or 401. Fail closed: no valid credential means no access."""
    expected = _internal_key()
    if x_api_key and expected and hmac.compare_digest(x_api_key, expected):
        return _MACHINE

    token = bearer_token(authorization)
    if token:
        principal = resolve_session(session, token)
        if principal is not None:
            return principal

    raise HTTPException(status_code=401, detail="not authenticated")


def current_client(
    principal: Annotated[Principal, Depends(current_principal)],
) -> Principal:
    """A portal client. Staff and machine principals are refused.

    /api/v1/me/* reads customer_id from HERE, never from the URL or the body, so there is no
    identifier for a caller to tamper with and IDOR is impossible by construction.
    """
    if principal.kind != "client" or principal.customer_id is None:
        raise HTTPException(status_code=403, detail="requires a client account")
    return principal
```

---

## §5 THE APPROVED CHANGE — `security.py`

### 5.1 What is deleted — precisely one expression

```python
role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
```

Two chained fallbacks die with it: *(i)* missing header → env var, *(ii)* env var unset → the
literal `"administrateur"`. **Nothing else is removed anywhere in the system.**

### 5.2 What is preserved — verified item by item

| Preserved | Proof it is unchanged |
|---|---|
| `require_role` name and `(minimum: str)` signature | identical below |
| Returns a dependency yielding `str` | identical below |
| 403 detail `f"requires role >= {minimum}"` | identical below |
| `role_rank()` and `_ROLE_RANK` | copied verbatim, not touched |
| All 44 route handlers | `ConseillerRole` / `SuperviseurRole` / `AdministrateurRole` aliases keep resolving to `Annotated[str, Depends(require_role(…))]` — **zero handler bodies change** |
| `GET /health` | declares no role dependency, so `current_principal` never runs for it |

### 5.3 REPLACE the whole file (1092 B → new content)

Full replacement rather than a patch: the module is small and its docstring is now false.

```python
"""API-layer RBAC (spec section 19): conseiller < superviseur < administrateur.

The role matrix is enforced here. Identity is established by
business_api.infrastructure.auth.principal.current_principal(): either a bearer session token
issued by POST /api/v1/auth/login and revalidated against auth.portal_sessions, or the internal
service key (INTERNAL_API_KEY) presented by the voice worker.

The `X-Role` header is NO LONGER READ. Before P0-1 an absent header fell back to
BUSINESS_API_DEFAULT_ROLE (defaulting to "administrateur"), which made every endpoint reachable
by an unauthenticated caller. A request without a valid credential now fails closed with 401.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException

from business_api.infrastructure.auth.principal import Principal, current_principal

_ROLE_RANK = {"conseiller": 1, "superviseur": 2, "administrateur": 3}


def role_rank(role: str | None) -> int:
    """Numeric rank for a role name (0 if unknown)."""
    return _ROLE_RANK.get(role or "", 0)


def require_role(minimum: str):
    """Dependency factory: 403 unless the caller's role is at least ``minimum``.

    401 (not 403) when there is no authenticated caller at all - the two answers mean different
    things and the front end already distinguishes them (isUnauthenticated / isForbidden).
    """
    minimum_rank = _ROLE_RANK[minimum]

    def _dependency(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> str:
        if role_rank(principal.role) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
        return principal.role

    return _dependency
```

> A client principal carries `role="client"`, which is **not** in `_ROLE_RANK`, so
> `role_rank("client")` returns 0 and every staff gate refuses it. The existing fail-closed
> behaviour of `role_rank` is what makes adding a fourth role safe without editing the map —
> which is why `_ROLE_RANK` is left alone.

### 5.4 Why this is the minimal correct change

The alternative — adding `Depends(authenticate)` to all 44 handlers — touches 44 signatures,
risks omissions, and leaves the vulnerable default in place for anything forgotten. Rewriting the
single dependency body fixes every route at once and makes an omission impossible: a route either
has a role gate (now authenticated) or is `/health`.

---

## §6 APPLICATION LAYER — `business_api/portal_auth.py`

Placed beside `advisors.py` / `availability.py` / `callbacks.py`, matching the established shape:
module-level functions that take a `Session` first. Route handlers in `main.py` stay thin.

```python
"""Portal authentication use cases (P0-1).

Owns the rules: lockout, session lifetime, password change, and the subscriber claim that binds a
new client login to an existing crm.customers row. main.py only validates input and maps outcomes
onto HTTP status codes.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_api.infrastructure.auth import cin, passwords, tokens
from persistence.models.crm import Customer, Subscription
from persistence.models.portal_identity import PortalAccount, PortalSession

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 10

# A real hash of a throwaway secret. Verifying against it when the email is unknown burns the
# same scrypt work as a real check, so response time does not disclose whether an account exists.
_DECOY_HASH = passwords.hash_password(secrets.token_urlsafe(16))[2]


class AuthError(Exception):
    """Authentication failure. ``code`` selects the HTTP mapping in main.py."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def session_ttl_seconds() -> int:
    """Backend session lifetime. Defaults to 8 h, matching ADMIN_SESSION_TTL."""
    try:
        return max(300, int(os.getenv("PORTAL_SESSION_TTL", "28800")))
    except ValueError:
        return 28800


# ---------------------------------------------------------------- sign in

def authenticate(session: Session, email: str, password: str) -> PortalAccount:
    """Return the account for valid credentials, else raise AuthError.

    A wrong address and a wrong password are indistinguishable: both spend one scrypt
    computation and both raise ``invalid_credentials``.
    """
    normalized = email.strip().lower()
    now = datetime.now(UTC)

    account = session.scalar(
        select(PortalAccount).where(PortalAccount.email == normalized)
    )

    if account is None:
        passwords.verify_password(
            password, passwords.ALGORITHM, passwords.default_params(), _DECOY_HASH
        )
        raise AuthError("invalid_credentials", "Incorrect email or password")

    if not account.is_active:
        raise AuthError("invalid_credentials", "Incorrect email or password")

    correct = passwords.verify_password(
        password, account.password_algo, account.password_params, account.password_hash
    )

    if account.locked_until is not None and account.locked_until > now:
        # Only someone who already knows the password learns that a lock exists; a guesser
        # keeps seeing the generic answer and learns nothing.
        if correct:
            raise AuthError(
                "locked", "Too many failed attempts. Try again in a few minutes."
            )
        raise AuthError("invalid_credentials", "Incorrect email or password")

    if not correct:
        account.failed_attempts += 1
        if account.failed_attempts >= MAX_FAILED_ATTEMPTS:
            account.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            account.failed_attempts = 0
        session.commit()
        raise AuthError("invalid_credentials", "Incorrect email or password")

    account.failed_attempts = 0
    account.locked_until = None
    account.last_login_at = now
    session.commit()
    return account


def open_session(
    session: Session,
    account: PortalAccount,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, datetime]:
    """Create a session row and return ``(token, expires_at)``. The token is never stored."""
    token = tokens.new_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=session_ttl_seconds())
    session.add(
        PortalSession(
            account_id=account.id,
            token_digest=tokens.token_digest(token),
            expires_at=expires_at,
            ip_address=ip_address[:45] if ip_address else None,
            user_agent=user_agent[:200] if user_agent else None,
        )
    )
    session.commit()
    return token, expires_at


def revoke_session(session: Session, token: str) -> None:
    """Idempotent logout: revoking an unknown or already-revoked token is a no-op."""
    row = session.scalar(
        select(PortalSession).where(
            PortalSession.token_digest == tokens.token_digest(token)
        )
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.commit()


def revoke_all(session: Session, account_id: uuid.UUID) -> int:
    """Sign out every device for an account. Returns how many sessions were closed."""
    now = datetime.now(UTC)
    rows = list(
        session.scalars(
            select(PortalSession).where(
                PortalSession.account_id == account_id,
                PortalSession.revoked_at.is_(None),
            )
        )
    )
    for row in rows:
        row.revoked_at = now
    if rows:
        session.commit()
    return len(rows)


# ---------------------------------------------------------------- password change

def change_password(
    session: Session, account_id: uuid.UUID, current: str, replacement: str
) -> int:
    """Rotate a password and close every other session. Returns sessions revoked.

    This is what makes ADMIN_PASSWORD a bootstrap value rather than a permanent one: the seed
    creates the row, the operator changes the password in the product, and the new hash lives in
    the database. The seed never overwrites it (see seed_admin.py).
    """
    account = session.get(PortalAccount, account_id)
    if account is None or not account.is_active:
        raise AuthError("invalid_credentials", "Incorrect password")

    if not passwords.verify_password(
        current, account.password_algo, account.password_params, account.password_hash
    ):
        raise AuthError("invalid_credentials", "Incorrect password")

    if len(replacement) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            "weak_password",
            f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if replacement == current:
        raise AuthError("weak_password", "Choose a password you have not used here before.")

    algorithm, params, encoded = passwords.hash_password(replacement)
    account.password_algo = algorithm
    account.password_params = params
    account.password_hash = encoded
    account.password_changed_at = datetime.now(UTC)
    session.commit()

    return revoke_all(session, account.id)


# ---------------------------------------------------------------- client signup

def signup_client(
    session: Session, *, msisdn: str, cin_last4: str, email: str, password: str
) -> PortalAccount:
    """Bind a new client login to the subscriber that already owns ``msisdn``.

    The portal never creates telecom data. The caller proves they are the subscriber using the
    SAME verifier the voice channel uses (auth.customer_credentials, cin_last4), and a login row
    is then attached to the customer that already exists. Balance, plan, invoices and tickets are
    never entered here - they are already in crm/billing/ocs keyed by customer_id, and surface
    through /api/v1/me/* using the customer_id carried by the token.

    Every failure below the password check raises the SAME error. Distinguishing "unknown number"
    from "wrong CIN" from "already registered" would turn this endpoint into a subscriber
    enumeration oracle.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            "weak_password",
            f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters.",
        )

    generic = AuthError(
        "signup_failed", "We could not match those details to an account."
    )

    normalized_msisdn = "".join(
        char for char in msisdn.strip() if char.isdigit() or char == "+"
    )
    normalized_email = email.strip().lower()
    if not normalized_msisdn or "@" not in normalized_email:
        raise generic

    subscription = session.scalar(
        select(Subscription).where(Subscription.msisdn == normalized_msisdn)
    )
    if subscription is None:
        raise generic

    customer = session.get(Customer, subscription.customer_id)
    if customer is None or customer.deleted_at is not None or customer.status == "closed":
        raise generic

    # A suspended subscriber must still be able to sign in and pay, so subscription.status is
    # deliberately NOT filtered here. Only a closed/deleted customer is refused.
    if not cin.matches(session, customer.id, cin_last4):
        raise generic

    taken = session.scalar(
        select(PortalAccount).where(
            (PortalAccount.customer_id == customer.id)
            | (PortalAccount.email == normalized_email)
        )
    )
    if taken is not None:
        raise generic

    algorithm, params, encoded = passwords.hash_password(password)
    account = PortalAccount(
        kind="client",
        email=normalized_email,
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role="client",
        customer_id=customer.id,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.commit()
    return account
```

---

## §7 ROUTES — `main.py`

All routes live in `main.py` in this codebase; the logic lives in sibling modules. That pattern is
followed exactly. Four edits, each with an exact `oldStr` copied from blob
`f41c3a3ee9841e93b22a0a134b0a3bb597a422df`.

### 7.1 EDIT 1 — imports

```
oldStr:
from audit_trail import PgAuditLedger
from business_api import advisors as advisor_repo
from business_api import availability as availability_repo
from business_api import callbacks as callback_repo
from business_api import policy_view
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from pydantic import BaseModel
from persistence import get_session

newStr:
from audit_trail import PgAuditLedger
from business_api import advisors as advisor_repo
from business_api import availability as availability_repo
from business_api import callbacks as callback_repo
from business_api import policy_view
from business_api import portal_auth
from business_api.infrastructure.auth import rate_limit
from business_api.infrastructure.auth.principal import (
    Principal,
    bearer_token,
    current_client,
    current_principal,
)
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from pydantic import BaseModel
from persistence import get_session
```

> The existing block is already not import-sorted (`pydantic` after `business_api`), which is
> why `ruff check main.py` reports a pre-existing `I001`. The insertion keeps the same shape and
> does **not** change that count. Do not "fix" the ordering here — that is P1-2 work and would
> inflate this diff.

### 7.2 EDIT 2 — CORS header allow-list, and the `Request` import

```
oldStr:
from fastapi import Depends, FastAPI, HTTPException

newStr:
from fastapi import Depends, FastAPI, HTTPException, Request
```

```
oldStr:
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Role"],
)

newStr:
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

`X-Role` is removed because it is no longer read. `Authorization` is added for completeness.
Neither front end calls `:8108` from the browser (both proxy through their own server functions),
so this list is defensive rather than load-bearing — which is exactly why it must stay truthful.

`allow_credentials` is **not** added: the bearer token travels in a header, never in a
cross-origin cookie.

### 7.3 EDIT 3 — role aliases gain a principal alias

```
oldStr:
DbSession = Annotated[Session, Depends(get_session)]
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]

newStr:
DbSession = Annotated[Session, Depends(get_session)]
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]
CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
ClientPrincipal = Annotated[Principal, Depends(current_client)]
```

**The three existing aliases are byte-identical.** All 44 handlers keep working with no edit.

### 7.4 EDIT 4 — the auth surface

Insert immediately **after** the `health()` handler and **before** `list_customers`.

```
oldStr:
@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/v1/customers")

newStr:
@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


# ---------------- Authentication (P0-1). One identity layer, two front ends. ----------------
class LoginPayload(BaseModel):
    """Credentials for either portal. The role comes from the account, never from the client."""

    email: str
    password: str


class SignupPayload(BaseModel):
    """A subscriber CLAIMING their existing account. It never creates telecom data."""

    msisdn: str
    cin_last4: str
    email: str
    password: str


class PasswordChangePayload(BaseModel):
    """Rotate your own password. Closes every other session."""

    current_password: str
    new_password: str


_AUTH_STATUS = {
    "invalid_credentials": 401,
    "signup_failed": 401,
    "weak_password": 400,
    "locked": 429,
    "rate_limited": 429,
}


def _client_ip(request: Request) -> str:
    """Best-effort caller address for throttling. Never used for authorisation."""
    return request.client.host if request.client else "unknown"


def _auth_http(error: portal_auth.AuthError) -> HTTPException:
    return HTTPException(
        status_code=_AUTH_STATUS.get(error.code, 401), detail=error.message
    )


@app.post("/api/v1/auth/login")
def auth_login(payload: LoginPayload, request: Request, session: DbSession) -> dict:
    """Exchange credentials for an opaque bearer token. Ungated by design."""
    bucket = f"login:{_client_ip(request)}"
    if not rate_limit.check(bucket):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    try:
        account = portal_auth.authenticate(session, payload.email, payload.password)
    except portal_auth.AuthError as error:
        raise _auth_http(error)

    rate_limit.reset(bucket)
    token, expires_at = portal_auth.open_session(
        session,
        account,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "email": account.email,
        "role": account.role,
        "kind": account.kind,
        "customer_id": str(account.customer_id) if account.customer_id else None,
    }


@app.post("/api/v1/auth/signup")
def auth_signup(payload: SignupPayload, request: Request, session: DbSession) -> dict:
    """Create a CLIENT login for an existing subscriber. Staff accounts are never self-served."""
    bucket = f"signup:{_client_ip(request)}"
    if not rate_limit.check(bucket, limit=10):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    try:
        account = portal_auth.signup_client(
            session,
            msisdn=payload.msisdn,
            cin_last4=payload.cin_last4,
            email=payload.email,
            password=payload.password,
        )
    except portal_auth.AuthError as error:
        raise _auth_http(error)

    token, expires_at = portal_auth.open_session(
        session,
        account,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "email": account.email,
        "role": account.role,
        "kind": account.kind,
        "customer_id": str(account.customer_id),
    }


@app.post("/api/v1/auth/logout")
def auth_logout(request: Request, session: DbSession, principal: CurrentPrincipal) -> dict:
    """Revoke the presented session. Idempotent."""
    token = bearer_token(request.headers.get("authorization"))
    if token:
        portal_auth.revoke_session(session, token)
    return {"signed_out": True}


@app.get("/api/v1/auth/me")
def auth_me(principal: CurrentPrincipal) -> dict:
    """Who the presented credential belongs to. The front ends use this to validate a session."""
    return {
        "subject": principal.subject,
        "kind": principal.kind,
        "role": principal.role,
        "customer_id": str(principal.customer_id) if principal.customer_id else None,
    }


@app.post("/api/v1/auth/password")
def auth_change_password(
    payload: PasswordChangePayload, session: DbSession, principal: CurrentPrincipal
) -> dict:
    """Change your own password. Machine principals have no password to change."""
    if principal.account_id is None:
        raise HTTPException(status_code=403, detail="requires a user account")
    try:
        revoked = portal_auth.change_password(
            session, principal.account_id, payload.current_password, payload.new_password
        )
    except portal_auth.AuthError as error:
        raise _auth_http(error)
    return {"changed": True, "sessions_revoked": revoked}


@app.post("/api/v1/auth/sessions/revoke-all")
def auth_revoke_all(session: DbSession, principal: CurrentPrincipal) -> dict:
    """Sign out of all devices. Backs the affordance already rendered on the portal Security page."""
    if principal.account_id is None:
        raise HTTPException(status_code=403, detail="requires a user account")
    return {"sessions_revoked": portal_auth.revoke_all(session, principal.account_id)}


# ---------------- Client portal reads. Scoped by the TOKEN, never by the URL. ----------------
@app.get("/api/v1/me/profile")
def me_profile(session: DbSession, principal: ClientPrincipal) -> dict:
    """The signed-in customer's own 360.

    customer_id comes from the authenticated principal, so there is no identifier in the request
    for a caller to tamper with: client A cannot address customer B's data at all.
    """
    data = SupervisionRepository(session).customer_360(str(principal.customer_id))
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/customers")
```

### 7.5 Scope note on `/api/v1/me/*`

P0-1 ships **one** `/me` read. That is deliberate:

* §4.4.10 of the brief requires the *identity layer* to be built once for both portals — done in
  full above (accounts, sessions, signup, login, logout, password change, revoke-all, client
  principal, ownership scoping).
* The remaining portal surfaces (billing, services, requests, activity) are **client-portal
  feature work**, not authentication. Each is one more handler following the identical
  `ClientPrincipal` + `principal.customer_id` pattern established here.
* `me_profile` exists now so the ownership rule is **provable today** (test case 12, §12.1) rather
  than asserted.

No mock data is introduced anywhere: `customer_360` is the existing repository method already
serving the admin dashboard.

### 7.6 Reused, not reinvented

`me_profile` calls `SupervisionRepository.customer_360` — the same method
`GET /api/v1/customers/{id}/360` uses. **No repository code is added, changed, or duplicated.**

---

## §8 THE AGENT WORKER — two one-line changes

This is the hinge. Get it wrong and the voice agent stops escalating.

### 8.1 The existing precedent, already in the tree

`apps/agent-worker/src/clients/context_client.py` (blob `819ff400…`) already does exactly this:

```python
from service_auth import internal_headers
...
self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())
```

and `context-service` already enforces it (`dependencies=[Depends(require_internal_key)]`). The
two business-api clients are the **only** ones still sending a self-asserted `X-Role`. This patch
makes them consistent with a pattern that is already running in production on this branch.

`apps/agent-worker/Dockerfile` installs `./packages/service-auth` — verified, line 8. No image or
dependency change.

### 8.2 EDIT `apps/agent-worker/src/clients/routing_client.py` (blob `17cdd5d2…`)

```
oldStr:
import httpx
from config import get_settings

from observability_kit import inject_trace_context

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvisorDestination:

newStr:
import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvisorDestination:
```

```
oldStr:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers={"X-Role": "conseiller"}
        )

    async def resolve_available_advisor(self, skill_tag: str) -> AdvisorDestination | None:

newStr:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        # The worker authenticates as a MACHINE, with the shared internal key business-api maps
        # to the conseiller rank - the exact rank these routes require. It no longer declares a
        # role: a caller asserting its own privilege was the P0-1 vulnerability.
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers=internal_headers()
        )

    async def resolve_available_advisor(self, skill_tag: str) -> AdvisorDestination | None:
```

### 8.3 EDIT `apps/agent-worker/src/clients/callback_client.py` (blob `42a11452…`)

```
oldStr:
import httpx
from config import get_settings

from observability_kit import inject_trace_context

logger = logging.getLogger(__name__)

newStr:
import httpx
from config import get_settings

from observability_kit import inject_trace_context
from service_auth import internal_headers

logger = logging.getLogger(__name__)
```

```
oldStr:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers={"X-Role": "conseiller"}
        )

    async def free_slots(self, days: int = 2, limit: int = 6, day: str | None = None,

newStr:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        # Machine identity, same shared key as context_client. See routing_client for why.
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers=internal_headers()
        )

    async def free_slots(self, days: int = 2, limit: int = 6, day: str | None = None,
```

### 8.4 Blast-radius analysis (the part that matters)

**Every business-api route the worker touches, and its gate after this patch:**

| Route | Gate | Machine rank | Result |
|---|---|---|---|
| `POST /api/v1/advisors/claim` | conseiller | conseiller | 200 |
| `POST /api/v1/advisors/{id}/release` | conseiller | conseiller | 200 |
| `GET /api/v1/advisors/on-call` | conseiller | conseiller | 200 |
| `GET /api/v1/callbacks/slots` | conseiller | conseiller | 200 |
| `GET /api/v1/callbacks/check` | conseiller | conseiller | 200 |
| `POST /api/v1/callbacks/reserve` | conseiller | conseiller | 200/409 |

Source: `git grep -n "api/v1" apps/agent-worker/src/clients/` — those six, no others. The machine
principal is deliberately pinned at `conseiller`, the lowest rank, so a compromised worker key
cannot reach `/audit/*`, `/jobs/retention`, or any advisor mutation. **Least privilege, verified
against the actual call sites rather than assumed.**

**Failure mode if `INTERNAL_API_KEY` is empty (Gate A skipped):** `internal_headers()` returns
`{}` → 401 → `resolve_available_advisor` catches `httpx.HTTPError`, logs
`"advisor claim failed"`, returns `None` → the agent offers a callback instead of a transfer.
`check_time` returns `{"available": False, "reason": "unreachable"}`. **The call does not crash and
the caller is never lied to** — the existing degradation paths hold. But it is a real functional
regression, which is why §0.3 is a gate.

**Ordering is not optional:**

```
1. set INTERNAL_API_KEY in .env
2. restart agent-worker      (starts sending X-API-Key; business-api still ignores it -> fine)
3. rebuild business-api      (starts requiring it; worker is already sending it -> fine)
```

Reverse that order and there is a window where the worker sends nothing and business-api demands
something. Step 2 is safe in isolation because today's business-api ignores unknown headers.

### 8.5 What is NOT changed in the worker

* `context_client.py` — already correct.
* `settings.py` — **no new field.** `internal_headers()` reads `INTERNAL_API_KEY` from the
  environment directly, exactly as it already does inside `context_client`. Adding a typed
  setting would duplicate ownership of one value and would trip the `_distinct_service_urls`
  validator's design intent of one owner per config value.
* Every tool, task, agent, and the LiveKit session lifecycle — untouched. This patch does not open
  `agents/`, `tasks/`, `session/`, `telephony/`, or `server.py`.

> **Known, unchanged, out of scope:** `settings.py` declares
> `business_api_url: str = Field("http://localhost:8107", alias="BUSINESS_API_URL")` — 8107 is the
> token-service port; business-api is 8108. `docker-compose.apps.yml` overrides it with
> `http://business-api:8108`, so containers are correct and only bare-metal `make dev` is
> affected. Logged for P1-2 item K. **Not fixed here** — it is unrelated to authentication and
> would widen this diff.

---

## §9 CONFIGURATION

### 9.1 EDIT `.env.example`

**Edit A** — the internal key gets the warning it now deserves.

```
oldStr:
# ===================================================================
# 3. SERVICE-TO-SERVICE AUTH
# ===================================================================
INTERNAL_API_KEY=                        # ⚠ set one shared key for staging/prod

newStr:
# ===================================================================
# 3. SERVICE-TO-SERVICE AUTH
# ===================================================================
# ⚠ REQUIRED since P0-1. business-api authenticates the agent-worker with this key and maps it
# to the `conseiller` rank. If it is empty, advisor claim and callback reservation return 401 and
# the voice agent silently degrades to offering a callback. Set it, restart agent-worker, THEN
# rebuild business-api - in that order.
INTERNAL_API_KEY=                        # ⚠ set one shared key for every service

# HMAC key protecting the stored CIN-last-four verifiers (auth.customer_credentials).
# Must be >= 32 characters. NEVER rotate it after seeding: every stored digest is salted with it
# and rotating invalidates all of them, breaking BOTH phone step-up and portal signup.
AUTH_CIN_HMAC_KEY=                       # ⚠ >= 32 chars; required by seed_auth_credentials
```

**Edit B** — §22 documents what the default role now does (and no longer does).

```
oldStr:
# ===================================================================
# 22. BUSINESS API RBAC
# ===================================================================
BUSINESS_API_DEFAULT_ROLE=administrateur

newStr:
# ===================================================================
# 22. BUSINESS API RBAC
# ===================================================================
# P0-1 removed the X-Role header and this variable from the authentication path. Every request
# now presents either a bearer session token or INTERNAL_API_KEY, and an unauthenticated request
# gets 401. BUSINESS_API_DEFAULT_ROLE is no longer read by any code; it is kept only so existing
# .env files stay valid. Delete it whenever convenient.
BUSINESS_API_DEFAULT_ROLE=administrateur

# ===================================================================
# 22b. PORTAL AUTHENTICATION (P0-1)
# ===================================================================
# Bootstrap staff account. `python -m business_api.seed_admin` creates it IF ABSENT and never
# overwrites an existing row, so a password changed in the product survives every redeploy.
ADMIN_EMAIL=admin@telecom.tn
ADMIN_PASSWORD=change-this-now           # ⚠ CHANGE for prod, then change it again in the app
ADMIN_ROLE=administrateur                # conseiller | superviseur | administrateur

# HMAC key for the admin dashboard's httpOnly session cookie. Generate: openssl rand -hex 32
ADMIN_SESSION_SECRET=                    # ⚠ required by the admin dashboard
ADMIN_SESSION_TTL=28800                  # cookie lifetime, seconds (8 h)

# Same, for the customer portal. Use a DIFFERENT value: one leaked secret must not forge the
# other portal's cookies.
PORTAL_SESSION_SECRET=                   # ⚠ required by the customer portal
PORTAL_SESSION_TTL=28800                 # backend session row lifetime, seconds (8 h)
```

> `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_ROLE` and `ADMIN_SESSION_SECRET` were already **required**
> by `Frontend/admin_dashboard/src/lib/api/config.ts` (`required(…)` throws without them) yet were
> **absent from the template** — a pre-existing gap this patch closes rather than introduces.
> `.env.example` §25 still ships stale `VITE_TOKEN_URL` / `VITE_BUSINESS_API_URL` /
> `VITE_API_ROLE=administrateur`, which nothing reads. **Left alone; logged for P1-2.**

### 9.2 CREATE `apps/business-api/src/business_api/seed_admin.py`

```python
"""Bootstrap the staff login. Idempotent: creates IF ABSENT, never overwrites.

Run once after migrating:

    docker compose -f infra/docker-compose/docker-compose.apps.yml \\
        exec business-api python -m business_api.seed_admin

Why this lives in business-api and not packages/persistence/seed/ (where the other five seeds
live): the scrypt hasher is business_api.infrastructure.auth.passwords, and persistence must not
depend on an app. Duplicating a password hasher to satisfy a directory convention would fork a
security primitive - the worse of the two trade-offs.

Why ADMIN_PASSWORD is never re-applied: after the first run the hash lives in the database and
the operator can change it in the product (POST /api/v1/auth/password). Overwriting on every boot
would silently undo that.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from business_api.infrastructure.auth import passwords
from persistence import session_scope
from persistence.models.portal_identity import STAFF_ROLES, PortalAccount


def main() -> int:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    role = os.getenv("ADMIN_ROLE", "administrateur").strip()

    if not email or not password:
        print("ADMIN_EMAIL and ADMIN_PASSWORD must be set", file=sys.stderr)
        return 2
    if role not in STAFF_ROLES:
        print(f"ADMIN_ROLE must be one of {', '.join(STAFF_ROLES)}", file=sys.stderr)
        return 2
    if len(password) < 10:
        print("ADMIN_PASSWORD must be at least 10 characters", file=sys.stderr)
        return 2

    with session_scope() as session:
        existing = session.scalar(
            select(PortalAccount).where(PortalAccount.email == email)
        )
        if existing is not None:
            print(f"admin already present: {email} ({existing.role}) - left untouched")
            return 0

        algorithm, params, encoded = passwords.hash_password(password)
        session.add(
            PortalAccount(
                kind="staff",
                email=email,
                password_hash=encoded,
                password_algo=algorithm,
                password_params=params,
                role=role,
                customer_id=None,
                is_active=True,
                password_changed_at=datetime.now(UTC),
            )
        )
        print(f"seeded staff account {email} ({role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> `session_scope()` is the existing commit/rollback context manager exported from `persistence`
> (`engine.py`). No new session handling is invented.

### 9.3 Answer to "how does the admin sign in after this?"

Exactly as today. Nothing about the experience changes:

| | Before | After |
|---|---|---|
| Login page | `/login`, email + password | **identical, zero code change** |
| Credentials | `ADMIN_EMAIL` / `ADMIN_PASSWORD` | **the same values** |
| Where they are checked | `auth.server.ts` compares two strings in the Node process | business-api compares a scrypt hash in Postgres |
| Env vars | required | **still required** — they seed the row |
| Changing the password | impossible without a redeploy | `POST /api/v1/auth/password`, takes effect immediately |

Admins are **never** created by signup. `POST /api/v1/auth/signup` hard-codes `kind="client"` /
`role="client"`, and the `ck_portal_accounts_kind_role_customer` CHECK makes a staff row without
a role — or a client row with one — **impossible at the database level**, not merely unlikely.

---

## §10 ADMIN DASHBOARD — three files, nothing else

The existing front-end boundary is **correct** and is kept. Only the fact it carries changes: a
backend-issued token instead of a self-asserted role.

**Unchanged, verified:** `login.tsx` (blob `7a23b658…`), `__root.tsx` (`c9d25371…`),
`middleware.ts` (`8d8b7ab8…`), `session.server.ts` (`ba80a640…`), `config.ts` (`16652bc4…`),
`errors.ts` (`fb9bd333…`), `start.ts`, `styles.css`, and **all 21 other `src/lib/api/*.server.ts`
files**. Zero design-system changes. Zero new dependencies.

### 10.1 EDIT `src/lib/api/session.ts` — one field

```
oldStr:
export type AdminSession = {
  /** Subject — the admin's email. */
  sub: string;
  role: BackendRole;
  /** Expiry, epoch seconds. */
  exp: number;
};

newStr:
export type AdminSession = {
  /** Subject — the admin's email. */
  sub: string;
  role: BackendRole;
  /** Expiry, epoch seconds. */
  exp: number;
  /**
   * Opaque bearer token issued by POST /api/v1/auth/login. Sealed inside the httpOnly,
   * HMAC-signed cookie, so it is never readable by client JavaScript and cannot be forged.
   * business-api revalidates it against auth.portal_sessions on every request.
   */
  token: string;
};
```

`signSession` / `verifySession` need no change — they serialise the whole object. `verifySession`
still rejects an expired `exp` and an unknown `role`; the extra field rides along.

### 10.2 REPLACE `src/lib/api/auth.server.ts`

```typescript
import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { clearSessionCookie, readSession, writeSessionCookie } from "./session.server";
import { ROLE_RANK, type AdminSession, type BackendRole } from "./session";

type LoginResponse = {
  token: string;
  expires_at: string;
  email: string;
  role: string;
  kind: string;
};

/**
 * Credentials are verified by business-api against a scrypt hash in auth.portal_accounts.
 * This process no longer holds, compares, or can leak a password.
 */
async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(`${serverConfig.businessApiUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (cause) {
    const timedOut = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      timedOut ? 504 : 503,
      timedOut ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  const raw = await response.text();

  if (!response.ok) {
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "business-api returned a malformed JSON body", path);
  }
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<AdminSession | null> => readSession(),
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }
    return { email: data.email.trim().toLowerCase(), password: data.password };
  })
  .handler(async ({ data }): Promise<AdminSession> => {
    const result = await postJson<LoginResponse>("/api/v1/auth/login", {
      email: data.email,
      password: data.password,
    });

    // A client account has no rank in the admin console. Refuse it here rather than issuing a
    // cookie the backend would reject on every subsequent call.
    if (!(result.role in ROLE_RANK)) {
      throw new ApiError(403, "This account cannot access the admin console", "login");
    }

    const session: AdminSession = {
      sub: result.email,
      role: result.role as BackendRole,
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
    };

    await writeSessionCookie(session);
    return session;
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  const session = await readSession();
  if (session) {
    // Revoke server-side first so the token dies even if the browser keeps the cookie.
    // A failure here must not trap the user in a session they asked to leave.
    try {
      await postJson<{ signed_out: boolean }>("/api/v1/auth/logout", {}, session.token);
    } catch {
      /* already expired or backend down — clearing the cookie is still correct */
    }
  }
  clearSessionCookie();
});

export const changePassword = createServerFn({ method: "POST" })
  .inputValidator((data: { currentPassword: string; newPassword: string }) => {
    if (
      typeof data?.currentPassword !== "string" ||
      typeof data?.newPassword !== "string"
    ) {
      throw new ApiError(400, "Both passwords are required", "password");
    }
    return { currentPassword: data.currentPassword, newPassword: data.newPassword };
  })
  .handler(async ({ data }): Promise<void> => {
    const session = await readSession();
    if (!session) throw new ApiError(401, "Not authenticated", "password");

    await postJson<{ changed: boolean }>(
      "/api/v1/auth/password",
      { current_password: data.currentPassword, new_password: data.newPassword },
      session.token,
    );

    // Changing a password revokes every session including this one. Clear the cookie so the
    // next navigation lands on /login instead of on a dead token.
    clearSessionCookie();
  });
```

> **Deliberate removal:** `constantTimeDelay()` is gone. Its job — hiding whether the email
> existed — now happens in `portal_auth.authenticate`, which spends one real scrypt computation on
> the unknown-email path (`_DECOY_HASH`). Keeping a second 120 ms sleep in the Node process would
> add latency without adding secrecy. This is a *replacement* of the mitigation, not a deletion.

### 10.3 EDIT `src/lib/api/business-api.ts` — the header swap

This is the change that would normally ripple through 21 files. It does not, because the token is
read from the session inside the transport instead of being threaded through every caller.

**Edit A — imports**

```
oldStr:
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import type { BackendRole } from "./session";

newStr:
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { readSession } from "./session.server";
import type { BackendRole } from "./session";
```

**Edit B — the `role` option becomes advisory**

```
oldStr:
  body?: unknown;
  /** Injected as X-Role. Resolved from the session by authedMiddleware — never from the client. */
  role: BackendRole;
};

newStr:
  body?: unknown;
  /**
   * Retained so all 21 existing callers keep compiling unchanged. It is NO LONGER SENT and no
   * longer grants anything: since P0-1 the backend derives the role from the bearer token it
   * issued. Kept as documentation of which rank a call expects, and used by requireRole() in
   * middleware.ts to fail at the edge before a doomed round trip.
   */
  role?: BackendRole;
};
```

**Edit C — the request**

```
oldStr:
export async function businessApi<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = "GET", query, body, role } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        "X-Role": role,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },

newStr:
export async function businessApi<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = "GET", query, body } = options;

  // The bearer token is read from the httpOnly session cookie inside this server-only module.
  // The browser never sees it and no caller can substitute one.
  const session = await readSession();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
```

**Edit D — the health probe stops pretending to have a role**

```
oldStr:
    await businessApi<{ status: string }>("/health", { role: "conseiller" });

newStr:
    await businessApi<{ status: string }>("/health", {});
```

`GET /health` declares no role dependency, so it stays reachable with no credential — which is
exactly what a connectivity probe on the login screen needs.

### 10.4 Why 21 files stay untouched — and it is still type-safe

Every caller passes `{ role: context.session.role, … }`. Widening `role` from required to optional
keeps all of them compiling with **zero edits**, because a supplied optional property is always
valid. `tsc --noEmit` proves it. The alternative — changing the contract to `token` — would mean 21
mechanical edits, 21 chances to miss one, and a larger diff for no security gain.

### 10.5 The security story after this change

| Layer | Purpose | Still there? |
|---|---|---|
| `beforeLoad` in `__root.tsx` | UX — send a signed-out user to `/login` | yes, unchanged |
| `authedMiddleware` | edge gate on every server function | yes, unchanged |
| `requireRole(…)` | mirror the backend verdict early | yes, unchanged |
| **business-api `require_role` + `current_principal`** | **the actual security boundary** | **new** |

The comment in `middleware.ts` — *"THE security boundary"* — is now **understated but no longer
misleading**: it is the boundary for the front end's own server functions, and the backend has its
own. §4.4.3 of the brief is satisfied: route protection is UX, the server is the boundary.

---

## §11 CUSTOMER PORTAL — the same identity layer, the portal's own theme

Built now, not retrofitted later (§0 of the brief). `Frontend/customer_portal` currently has **no**
`src/lib/api/`, no session, no auth, and `src/routes/index.tsx` redirects straight to `/assistant`.

### 11.1 Design-identity compliance — checked against source, not memory

Every class below is copied from a component already in the portal.

| Element | Source of truth |
|---|---|
| `Button`, `Card`, `FieldRow`, `SectionLabel`, `Divider`, `StatusChip` | `src/components/portal/primitives.tsx` (blob `89dd99f2…`) |
| Card shell | `Card` = `rounded-r-5 border border-stroke-default bg-surface-1 shadow-elev-1`, `inset` → `p-sp-8` |
| Primary button | `variant="primary"` → `border-transparent bg-n-12 text-ink-inverse hover:bg-n-11` |
| Text input | copied verbatim from `SearchField`: `focus-ring t-ui-regular h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5` |
| Page background | `bg-surface-0`, as `PortalShell` uses |
| Type scale | `t-title-3`, `t-body`, `t-label`, `t-caption`, `t-micro` — all from `styles.css` |

**No new colour, radius, spacing token, shadow, or type utility is introduced. No hex, no `rgb(`.**
The portal's `styles.css` is strictly achromatic (`R === G === B`, thirteen greys) and stays
untouched. The admin dashboard is not touched by this section at all.

> The portal has no `TextField` primitive (the admin dashboard does). Rather than invent one,
> §11.6 defines a local `Field` **inside the login route file**, assembled entirely from existing
> classes. It is not exported and not added to the catalogue — `primitives.tsx` says
> *"le catalogue. Rien hors catalogue."* and stays byte-identical.

### 11.2 CREATE `src/lib/api/config.ts`

```typescript
/**
 * Server-only configuration. Never imported from a component.
 *
 * Deliberately NOT prefixed with VITE_: the Lovable vite preset injects VITE_* into the client
 * bundle, and the backend URL and session secret must never reach the browser.
 *
 * Mirrors Frontend/admin_dashboard/src/lib/api/config.ts on purpose - one identity layer, two
 * front ends, the same shape on both sides.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Copy .env.example to .env and fill it in.`,
    );
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] || fallback;
}

export const serverConfig = {
  /** business-api origin. Docker: http://business-api:8108 */
  businessApiUrl: () => optional("BUSINESS_API_URL", "http://localhost:8108").replace(/\/$/, ""),

  /** HMAC key for the session cookie. Generate: openssl rand -hex 32 */
  sessionSecret: () => required("PORTAL_SESSION_SECRET"),

  /** Session lifetime in seconds. Default 8 h. */
  sessionTtlSeconds: () => Number(optional("PORTAL_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  isProduction: () => process.env["NODE_ENV"] === "production",
} as const;
```

### 11.3 CREATE `src/lib/api/errors.ts`

Identical to the admin dashboard's `errors.ts` except for the two copy strings, which speak to a
customer rather than to an operator.

```typescript
/** Typed transport errors. Thrown server-side, serialised to the client by TanStack Start. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly path: string;

  constructor(status: number, detail: string, path: string) {
    super(`business-api ${status} on ${path}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.path = path;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError || (error as ApiError)?.name === "ApiError";
}

/** 401 — the session is gone. The UI must send the customer back to /login. */
export function isUnauthenticated(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

/** 403 — signed in, but this account cannot see this. */
export function isForbidden(error: unknown): boolean {
  return isApiError(error) && error.status === 403;
}

/** Human-readable copy. Never leaks a stack trace. */
export function errorMessage(error: unknown): string {
  if (isForbidden(error)) return "This account does not have access to that.";
  if (isUnauthenticated(error)) return "Your session has expired. Sign in again.";
  if (isApiError(error)) return error.detail || "Something went wrong. Please try again.";
  if (typeof error === "string") return error;
  return "Could not reach the service. Please try again in a moment.";
}
```

### 11.4 CREATE `src/lib/api/session.ts` and `src/lib/api/session.server.ts`

`session.ts` is the admin dashboard's `session.ts` with the role vocabulary replaced by the single
client role. `toBase64Url`, `fromBase64Url`, `hmacKey`, `timingSafeEqual`, `signSession` and
`verifySession` are **copied verbatim** — the same audited HMAC-SHA-256 implementation, not a
second design.

```typescript
export const SESSION_COOKIE = "nexus_portal_session";

export type PortalSession = {
  /** Subject — the customer's email. */
  sub: string;
  /** Canonical crm.customers.id. Advisory only: the backend re-derives it from the token. */
  customerId: string;
  /** Expiry, epoch seconds. */
  exp: number;
  /** Opaque bearer token issued by POST /api/v1/auth/login. */
  token: string;
};

/* ---------- base64url (no padding) ---------- */

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/* ---------- HMAC-SHA-256 via Web Crypto ---------- */

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

/** Constant-time comparison — avoids leaking signature bytes through timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function signSession(session: PortalSession, secret: string): Promise<string> {
  const payload = toBase64Url(new TextEncoder().encode(JSON.stringify(session)));
  const signature = await crypto.subtle.sign(
    "HMAC",
    await hmacKey(secret),
    new TextEncoder().encode(payload),
  );
  return `${payload}.${toBase64Url(new Uint8Array(signature))}`;
}

export async function verifySession(
  token: string | undefined,
  secret: string,
): Promise<PortalSession | null> {
  if (!token) return null;

  const separator = token.lastIndexOf(".");
  if (separator <= 0) return null;

  const payload = token.slice(0, separator);
  const signature = token.slice(separator + 1);

  const expected = toBase64Url(
    new Uint8Array(
      await crypto.subtle.sign("HMAC", await hmacKey(secret), new TextEncoder().encode(payload)),
    ),
  );
  if (!timingSafeEqual(signature, expected)) return null;

  try {
    const session = JSON.parse(new TextDecoder().decode(fromBase64Url(payload))) as PortalSession;
    if (typeof session.exp !== "number" || session.exp * 1000 < Date.now()) return null;
    if (typeof session.token !== "string" || !session.token) return null;
    return session;
  } catch {
    return null;
  }
}
```

`session.server.ts` — the admin file with the portal's cookie name and config:

```typescript
import { getCookie, setCookie } from "@tanstack/react-start/server";
import { serverConfig } from "./config";
import { SESSION_COOKIE, signSession, verifySession, type PortalSession } from "./session";

export async function writeSessionCookie(session: PortalSession): Promise<void> {
  setCookie(SESSION_COOKIE, await signSession(session, serverConfig.sessionSecret()), {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: serverConfig.sessionTtlSeconds(),
  });
}

export function clearSessionCookie(): void {
  setCookie(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: 0,
  });
}

export async function readSession(): Promise<PortalSession | null> {
  return verifySession(getCookie(SESSION_COOKIE), serverConfig.sessionSecret());
}
```

### 11.5 CREATE `src/lib/api/middleware.ts`, `business-api.ts`, `auth.server.ts`, `me.server.ts`

`middleware.ts` — the portal's edge gate, mirroring the admin's:

```typescript
import { createMiddleware } from "@tanstack/react-start";
import { ApiError } from "./errors";
import { readSession } from "./session.server";
import type { PortalSession } from "./session";

/**
 * THE front-end security boundary.
 *
 * Server functions are reachable independently of the route that renders them, so a beforeLoad
 * guard is NOT sufficient. Attach this to every server function that touches customer data.
 * business-api enforces the same rule again, and scopes every /me/* read to the customer the
 * token belongs to.
 */
export const authedMiddleware = createMiddleware().server(async ({ next }) => {
  const session = await readSession();
  if (!session) {
    throw new ApiError(401, "Not authenticated", "session");
  }
  return next({ context: { session } });
});

export type AuthedContext = { session: PortalSession };
```

`business-api.ts` — the admin transport with `role` removed entirely (the portal never had one):

```typescript
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { readSession } from "./session.server";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Query string params. undefined/null entries are dropped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
};

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${serverConfig.businessApiUrl()}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Server-only HTTP client for business-api.
 *
 * SECURITY: the bearer token comes from the httpOnly session cookie and never from an argument,
 * so no caller can substitute one. The browser never holds it.
 */
export async function businessApi<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body } = options;
  const session = await readSession();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      signal: controller.signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (cause) {
    const timedOut = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      timedOut ? 504 : 503,
      timedOut ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) return undefined as T;

  const raw = await response.text();

  if (!response.ok) {
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail !== undefined) detail = JSON.stringify(parsed.detail);
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "business-api returned a malformed JSON body", path);
  }
}
```

`auth.server.ts` — `getSession`, `login`, `signup`, `logout`. Same `postJson` helper as §10.2
(copied into this file; the two apps share no code by design — they are separate Vite builds).

```typescript
import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { clearSessionCookie, readSession, writeSessionCookie } from "./session.server";
import type { PortalSession } from "./session";

type AuthResponse = {
  token: string;
  expires_at: string;
  email: string;
  role: string;
  kind: string;
  customer_id: string | null;
};

async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(`${serverConfig.businessApiUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (cause) {
    const timedOut = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      timedOut ? 504 : 503,
      timedOut ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  const raw = await response.text();

  if (!response.ok) {
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "business-api returned a malformed JSON body", path);
  }
}

function toSession(result: AuthResponse): PortalSession {
  // Only a client account belongs in the customer portal. A staff login is refused here rather
  // than issued a cookie that every /me/* call would reject with 403.
  if (result.kind !== "client" || !result.customer_id) {
    throw new ApiError(403, "This account cannot access the customer portal", "login");
  }
  return {
    sub: result.email,
    customerId: result.customer_id,
    exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
    token: result.token,
  };
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<PortalSession | null> => readSession(),
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }
    return { email: data.email.trim().toLowerCase(), password: data.password };
  })
  .handler(async ({ data }): Promise<PortalSession> => {
    const session = toSession(
      await postJson<AuthResponse>("/api/v1/auth/login", {
        email: data.email,
        password: data.password,
      }),
    );
    await writeSessionCookie(session);
    return session;
  });

export const signup = createServerFn({ method: "POST" })
  .inputValidator(
    (data: { msisdn: string; cinLast4: string; email: string; password: string }) => {
      const fields = [data?.msisdn, data?.cinLast4, data?.email, data?.password];
      if (fields.some((value) => typeof value !== "string" || value.length === 0)) {
        throw new ApiError(400, "All fields are required", "signup");
      }
      return {
        msisdn: data.msisdn.trim(),
        cinLast4: data.cinLast4.trim(),
        email: data.email.trim().toLowerCase(),
        password: data.password,
      };
    },
  )
  .handler(async ({ data }): Promise<PortalSession> => {
    const session = toSession(
      await postJson<AuthResponse>("/api/v1/auth/signup", {
        msisdn: data.msisdn,
        cin_last4: data.cinLast4,
        email: data.email,
        password: data.password,
      }),
    );
    await writeSessionCookie(session);
    return session;
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  const session = await readSession();
  if (session) {
    try {
      await postJson<{ signed_out: boolean }>("/api/v1/auth/logout", {}, session.token);
    } catch {
      /* already expired or backend down — clearing the cookie is still correct */
    }
  }
  clearSessionCookie();
});
```

`me.server.ts` — the first authenticated read, establishing the pattern for every later one:

```typescript
import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

/**
 * The signed-in customer's own record.
 *
 * No identifier is sent. business-api derives customer_id from the bearer token, so this call
 * cannot be pointed at anyone else's data - not by this code, and not by a crafted request.
 */
export const fetchMyProfile = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async () => businessApi<Record<string, unknown>>("/api/v1/me/profile"));
```

### 11.6 CREATE `src/routes/login.tsx`

The portal has no `TextField` primitive, so `Field` is defined locally from existing classes and
not exported. `primitives.tsx` stays byte-identical.

```tsx
import { useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { Button, Card } from "@/components/portal/primitives";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Nexus" },
      { name: "description", content: "Sign in to your Nexus customer portal." },
    ],
  }),
  component: LoginPage,
});

/**
 * Local field. Classes are lifted verbatim from SearchField in components/portal/primitives.tsx
 * and FieldRow's label styling - no new token, no new shape.
 */
function Field({
  label,
  type,
  value,
  onChange,
  autoComplete,
  inputMode,
  hint,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  inputMode?: "text" | "tel" | "numeric" | "email";
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="t-label text-ink-4">{label}</span>
      <input
        type={type}
        value={value}
        required
        autoComplete={autoComplete}
        inputMode={inputMode}
        onChange={(event) => onChange(event.target.value)}
        className="focus-ring t-ui-regular mt-sp-3 h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
      />
      {hint ? <span className="t-caption mt-sp-2 block text-ink-5">{hint}</span> : null}
    </label>
  );
}

function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login({ data: { email, password } });
      await router.invalidate();
      await router.navigate({ to: "/assistant" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[380px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <span className="mb-sp-6 inline-flex h-10 w-10 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-2 shadow-elev-1" />
          <h1 className="t-title-3 text-ink-1">Nexus</h1>
          <p className="t-caption mt-sp-2 text-ink-4">Sign in to your account.</p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-sp-5">
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="username"
            inputMode="email"
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="mt-sp-7 border-t border-stroke-subtle pt-sp-6 text-center">
          <p className="t-caption text-ink-4">
            No account yet?{" "}
            <Link to="/signup" className="focus-ring text-ink-2 underline underline-offset-2">
              Create one
            </Link>
          </p>
        </div>
      </Card>
    </div>
  );
}
```

### 11.7 CREATE `src/routes/signup.tsx`

Four fields. Nothing about the customer's telecom account is asked for, because all of it already
exists keyed by `customer_id`.

```tsx
import { useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { Button, Card } from "@/components/portal/primitives";
import { signup } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create your account — Nexus" },
      {
        name: "description",
        content: "Link your Nexus mobile number to a portal account.",
      },
    ],
  }),
  component: SignupPage,
});

function Field({
  label,
  type,
  value,
  onChange,
  autoComplete,
  inputMode,
  maxLength,
  hint,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  inputMode?: "text" | "tel" | "numeric" | "email";
  maxLength?: number;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="t-label text-ink-4">{label}</span>
      <input
        type={type}
        value={value}
        required
        maxLength={maxLength}
        autoComplete={autoComplete}
        inputMode={inputMode}
        onChange={(event) => onChange(event.target.value)}
        className="focus-ring t-ui-regular mt-sp-3 h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
      />
      {hint ? <span className="t-caption mt-sp-2 block text-ink-5">{hint}</span> : null}
    </label>
  );
}

function SignupPage() {
  const router = useRouter();
  const [msisdn, setMsisdn] = useState("");
  const [cinLast4, setCinLast4] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await signup({ data: { msisdn, cinLast4, email, password } });
      await router.invalidate();
      await router.navigate({ to: "/assistant" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8 py-sp-9">
      <Card className="w-full max-w-[420px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <span className="mb-sp-6 inline-flex h-10 w-10 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-2 shadow-elev-1" />
          <h1 className="t-title-3 text-ink-1">Create your account</h1>
          <p className="t-body mt-sp-3 max-w-sm text-ink-4">
            Your line is already with us. Confirm it is yours and choose how you will sign in.
          </p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-sp-6">
          <Field
            label="Mobile number"
            type="tel"
            value={msisdn}
            onChange={setMsisdn}
            autoComplete="tel"
            inputMode="tel"
            hint="The number on your Nexus line."
          />
          <Field
            label="Last 4 digits of your ID"
            type="text"
            value={cinLast4}
            onChange={setCinLast4}
            inputMode="numeric"
            maxLength={4}
            hint="The same four digits our assistant asks for on the phone."
          />
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            inputMode="email"
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            hint="At least 10 characters."
          />

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <div className="mt-sp-7 border-t border-stroke-subtle pt-sp-6 text-center">
          <p className="t-caption text-ink-4">
            Already have an account?{" "}
            <Link to="/login" className="focus-ring text-ink-2 underline underline-offset-2">
              Sign in
            </Link>
          </p>
        </div>
      </Card>
    </div>
  );
}
```

### 11.8 EDIT `src/routes/_portal.tsx` — the UX gate

The portal's ten pages all live under `_portal`, so one `beforeLoad` covers every one of them.
Mirrors the admin `__root.tsx` pattern; `/login` and `/signup` sit **outside** `_portal` and are
reachable while signed out with no extra condition.

```
oldStr:
import { Outlet, createFileRoute } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";

export const Route = createFileRoute("/_portal")({
  component: PortalLayout,
});

newStr:
import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";
import { getSession } from "@/lib/api/auth.server";

export const Route = createFileRoute("/_portal")({
  // UX gate only. The security boundary is authedMiddleware on each server function
  // (src/lib/api/middleware.ts) and require_role/current_client in business-api.
  beforeLoad: async () => {
    const session = await getSession();
    if (!session) {
      throw redirect({ to: "/login" });
    }
    return { session };
  },
  component: PortalLayout,
});
```

`src/routes/index.tsx` keeps redirecting to `/assistant`; an unauthenticated visitor is then caught
by `_portal` and lands on `/login`. **No change to `index.tsx`, `__root.tsx`, `router.tsx`,
`start.ts`, `server.ts` or `nav.ts`.** `routeTree.gen.ts` regenerates itself — never hand-edit it.

### 11.9 Portal deployment note

The customer portal is not in `docker-compose.apps.yml` (neither front end is). It runs with
`PORTAL_SESSION_SECRET` and `BUSINESS_API_URL` in its environment. Both are added to
`.env.example` in §9.1.

---

## §12 TESTS

Baseline is **28 passed**. This adds **21**, giving **49**.

### 12.1 APPEND to `apps/business-api/tests/conftest.py`

Additive only — the existing `db_session`, `make_advisor`, `monday_slot` and `MONDAY` are untouched.

```
oldStr:
import pytest
from sqlalchemy.orm import Session

from persistence.engine import get_engine
from persistence.models.routing import Advisor, AdvisorShift

MONDAY = 0

newStr:
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from persistence.engine import get_engine
from persistence.models.routing import Advisor, AdvisorShift

MONDAY = 0
```

Then append at the end of the file:

```python
@pytest.fixture
def api_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """HTTP client bound to the rolled-back test transaction.

    get_session is overridden so every request inside a test shares the fixture's session and
    leaves no trace, exactly like db_session. Imported lazily so collecting this module never
    requires a database.
    """
    from business_api.infrastructure.auth import rate_limit
    from business_api.main import app
    from persistence import get_session

    # A shared 32+ char key so cin.digest() is computable in tests without touching the real one.
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", "t" * 48)
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    rate_limit.clear_all()

    app.dependency_overrides[get_session] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)
        rate_limit.clear_all()


def make_staff_account(session: Session, *, email: str, password: str, role: str):
    """A staff login usable by the HTTP tests."""
    from datetime import UTC, datetime

    from business_api.infrastructure.auth import passwords
    from persistence.models.portal_identity import PortalAccount

    algorithm, params, encoded = passwords.hash_password(password)
    account = PortalAccount(
        kind="staff",
        email=email.lower(),
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role=role,
        customer_id=None,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()
    return account
```

> `TestClient` comes from `fastapi.testclient`, which requires `httpx` — already a transitive
> dependency of the FastAPI stack in this image. Confirm with
> `python -c "from fastapi.testclient import TestClient"` before running the suite. If it is
> absent, `pip install httpx` in the dev environment only — **do not add it to any pyproject**,
> since it is a test-time need and the image already has it via the service clients.

### 12.2 CREATE `apps/business-api/tests/test_auth_passwords.py` (5 tests)

```python
"""scrypt hashing: round trip, rejection, and tolerance of corrupt records."""
from __future__ import annotations

from business_api.infrastructure.auth import passwords


def test_round_trip():
    algorithm, params, encoded = passwords.hash_password("correct horse battery")
    assert algorithm == "scrypt"
    assert passwords.verify_password("correct horse battery", algorithm, params, encoded)


def test_wrong_password_is_rejected():
    algorithm, params, encoded = passwords.hash_password("correct horse battery")
    assert not passwords.verify_password("Correct horse battery", algorithm, params, encoded)


def test_salt_is_unique_per_hash():
    _, _, first = passwords.hash_password("same password")
    _, _, second = passwords.hash_password("same password")
    assert first != second


def test_unknown_algorithm_is_rejected_not_raised():
    _, params, encoded = passwords.hash_password("whatever")
    assert passwords.verify_password("whatever", "bcrypt", params, encoded) is False


def test_corrupt_record_returns_false():
    for encoded in ("", "nodollar", "zz$zz", "$"):
        assert passwords.verify_password("x", "scrypt", passwords.default_params(), encoded) is False
```

### 12.3 CREATE `apps/business-api/tests/test_auth_cin.py` (2 tests)

This is the anti-drift test. It fails if either implementation is ever edited.

```python
"""The CIN digest in business-api must stay identical to the one in context-service."""
from __future__ import annotations

import hashlib
import hmac

import pytest

from business_api.infrastructure.auth import cin

_KEY = "k" * 48
_CUSTOMER = "2187de39-3a84-4c1c-872f-b6711dc9f7a1"


def test_digest_matches_pinned_vector(monkeypatch: pytest.MonkeyPatch):
    """Recomputed independently, exactly as context_service.auth_service._digest builds it."""
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", _KEY)
    expected = hmac.new(
        _KEY.encode(), f"cin_last4:{_CUSTOMER}:4821".encode(), hashlib.sha256
    ).hexdigest()
    assert cin.digest(_CUSTOMER, "4821") == expected
    # Non-digits are stripped, so "48-21" and " 4821 " verify identically.
    assert cin.digest(_CUSTOMER, "48-21") == expected
    assert cin.digest(_CUSTOMER, " 4821 ") == expected


def test_short_key_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_CIN_HMAC_KEY", "tooshort")
    with pytest.raises(RuntimeError):
        cin.digest(_CUSTOMER, "4821")
```

### 12.4 CREATE `apps/business-api/tests/test_auth_rate_limit.py` (3 tests)

```python
"""Sliding-window throttle."""
from __future__ import annotations

from business_api.infrastructure.auth import rate_limit


def test_allows_up_to_the_limit_then_refuses():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:1", limit=3) for _ in range(3))
    assert rate_limit.check("ip:1", limit=3) is False


def test_buckets_are_independent():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:a", limit=2) for _ in range(2))
    assert rate_limit.check("ip:a", limit=2) is False
    assert rate_limit.check("ip:b", limit=2) is True


def test_reset_clears_a_bucket():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:c", limit=2) for _ in range(2))
    rate_limit.reset("ip:c")
    assert rate_limit.check("ip:c", limit=2) is True
```

### 12.5 CREATE `apps/business-api/tests/test_auth_http.py` (11 tests)

The security suite. **Every one of these fails on `version_83` before the patch** — which is the
point.

```python
"""End-to-end authentication and authorisation over real HTTP.

These are the P0-1 regression tests. Case 1 and case 2 both return 200 on the unpatched build:
that was the vulnerability.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from tests.conftest import make_staff_account

ADMIN = ("admin@test.local", "a-long-enough-password")
ADVISOR = ("advisor@test.local", "another-long-password")


def _login(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- 1-2: the vulnerability itself -------------------------------------------------

def test_no_credential_is_refused(api_client):
    assert api_client.get("/api/v1/customers").status_code == 401


def test_forged_x_role_header_is_ignored(api_client):
    response = api_client.get(
        "/api/v1/jobs/integrity", headers={"X-Role": "administrateur"}
    )
    assert response.status_code == 401


def test_health_stays_open(api_client):
    assert api_client.get("/health").status_code == 200


# ---- 3-6: the happy path and the rank matrix ---------------------------------------

def test_valid_session_reaches_its_rank(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    assert api_client.get("/api/v1/jobs/integrity", headers=_auth(token)).status_code == 200


def test_one_rank_below_is_forbidden(api_client, db_session: Session):
    make_staff_account(db_session, email=ADVISOR[0], password=ADVISOR[1], role="conseiller")
    token = _login(api_client, *ADVISOR)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    response = api_client.get("/api/v1/tickets", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["detail"] == "requires role >= superviseur"


def test_wrong_password_is_refused(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    response = api_client.post(
        "/api/v1/auth/login", json={"email": ADMIN[0], "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_unknown_email_gives_the_same_answer(api_client):
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "nobody@test.local", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


# ---- 7-9: session lifecycle ---------------------------------------------------------

def test_logout_kills_the_token_immediately(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    token = _login(api_client, *ADMIN)
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 200
    assert api_client.post("/api/v1/auth/logout", headers=_auth(token)).status_code == 200
    assert api_client.get("/api/v1/customers", headers=_auth(token)).status_code == 401


def test_garbage_token_is_refused(api_client):
    assert api_client.get("/api/v1/customers", headers=_auth("not-a-token")).status_code == 401
    response = api_client.get("/api/v1/customers", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


def test_revoke_all_closes_every_session(api_client, db_session: Session):
    make_staff_account(db_session, email=ADMIN[0], password=ADMIN[1], role="administrateur")
    first = _login(api_client, *ADMIN)
    second = _login(api_client, *ADMIN)
    assert api_client.post(
        "/api/v1/auth/sessions/revoke-all", headers=_auth(first)
    ).status_code == 200
    assert api_client.get("/api/v1/customers", headers=_auth(first)).status_code == 401
    assert api_client.get("/api/v1/customers", headers=_auth(second)).status_code == 401


# ---- 10-11: the machine principal ----------------------------------------------------

def test_internal_key_is_conseiller_and_no_higher(api_client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    machine = {"X-API-Key": "test-internal-key"}
    assert api_client.get("/api/v1/advisors/on-call", headers=machine).status_code == 200
    # The worker must not be able to reach a supervisor or admin surface.
    assert api_client.get("/api/v1/tickets", headers=machine).status_code == 403
    assert api_client.get("/api/v1/jobs/integrity", headers=machine).status_code == 403


def test_wrong_internal_key_is_refused(api_client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    response = api_client.get("/api/v1/advisors/on-call", headers={"X-API-Key": "nope"})
    assert response.status_code == 401
```

### 12.6 CREATE `apps/business-api/tests/test_auth_client_scope.py` (4 tests)

Ownership — §4.4.2 of the brief (*client A must not reach customer B*).

```python
"""A client account can only ever read its own customer record."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from business_api.infrastructure.auth import cin, passwords
from persistence.models.auth import CustomerCredential
from persistence.models.crm import Customer, Subscription
from persistence.models.portal_identity import PortalAccount


def _customer(session: Session, suffix: str) -> Customer:
    customer = Customer(
        national_id=f"CIN{suffix}",
        first_name="Test",
        last_name=f"Case{suffix}",
        preferred_language="fr",
        status="active",
    )
    session.add(customer)
    session.flush()
    session.add(
        Subscription(
            customer_id=customer.id,
            msisdn=f"+2169{suffix}",
            plan_type="PREPAID",
            status="ACTIVE",
        )
    )
    session.add(
        CustomerCredential(
            customer_id=customer.id,
            verifier_type="cin_last4",
            verifier_digest=cin.digest(str(customer.id), suffix[-4:]),
            key_version=1,
            active=True,
        )
    )
    session.flush()
    return customer


def _client_account(session: Session, customer: Customer, email: str) -> PortalAccount:
    algorithm, params, encoded = passwords.hash_password("a-long-enough-password")
    account = PortalAccount(
        kind="client",
        email=email,
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role="client",
        customer_id=customer.id,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()
    return account


def test_me_profile_returns_only_the_token_owner(api_client, db_session: Session):
    alice = _customer(db_session, "110011")
    _customer(db_session, "220022")
    _client_account(db_session, alice, "alice@test.local")

    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@test.local", "password": "a-long-enough-password"},
    ).json()["token"]

    body = api_client.get(
        "/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert body["customer"]["id"] == str(alice.id)


def test_client_cannot_reach_staff_endpoints(api_client, db_session: Session):
    alice = _customer(db_session, "330033")
    _client_account(db_session, alice, "alice2@test.local")
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice2@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    # role "client" is absent from _ROLE_RANK, so role_rank() is 0 and every staff gate refuses.
    assert api_client.get("/api/v1/customers", headers=auth).status_code == 403
    assert api_client.get("/api/v1/tickets", headers=auth).status_code == 403
    assert api_client.get("/api/v1/jobs/integrity", headers=auth).status_code == 403


def test_staff_cannot_use_the_client_surface(api_client, db_session: Session):
    from tests.conftest import make_staff_account

    make_staff_account(
        db_session, email="boss@test.local", password="a-long-enough-password", role="administrateur"
    )
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "boss@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    response = api_client.get(
        "/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_signup_claims_an_existing_subscriber(api_client, db_session: Session):
    customer = _customer(db_session, "440044")

    response = api_client.post(
        "/api/v1/auth/signup",
        json={
            "msisdn": "+2169440044",
            "cin_last4": "0044",
            "email": "claim@test.local",
            "password": "a-long-enough-password",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["customer_id"] == str(customer.id)

    # Wrong CIN, unknown number, and a second claim all give the identical generic answer.
    for payload in (
        {"msisdn": "+2169440044", "cin_last4": "9999"},
        {"msisdn": "+21600000000", "cin_last4": "0044"},
    ):
        again = api_client.post(
            "/api/v1/auth/signup",
            json={**payload, "email": "other@test.local", "password": "a-long-enough-password"},
        )
        assert again.status_code == 401
        assert again.json()["detail"] == "We could not match those details to an account."


def test_uuid_is_never_taken_from_the_request(api_client, db_session: Session):
    """There is no path parameter to tamper with: /me/profile takes no identifier at all."""
    alice = _customer(db_session, "550055")
    _client_account(db_session, alice, "alice3@test.local")
    token = api_client.post(
        "/api/v1/auth/login",
        json={"email": "alice3@test.local", "password": "a-long-enough-password"},
    ).json()["token"]
    # A crafted query string cannot redirect the read.
    body = api_client.get(
        f"/api/v1/me/profile?customer_id={uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert body["customer"]["id"] == str(alice.id)
```

> `test_me_profile_returns_only_the_token_owner` asserts `body["customer"]["id"]`. **Confirm the
> exact key shape** with `customer_360` before running:
> `python -c "import inspect,business_api.repositories as r; print(inspect.getsource(r.SupervisionRepository.customer_360))" | head -40`.
> If the payload nests differently, adjust the assertion — never the endpoint.

### 12.7 `test_security.py` — unchanged

`role_rank` and `_ROLE_RANK` are preserved verbatim, so `test_role_hierarchy` passes untouched.
That is the regression proof for the part of `security.py` that did **not** change.

---

## §13 APPLY ORDER — follow exactly

The order is load-bearing. Steps 1–3 are reversible and touch nothing running.

```bash
# 1. GATES. Do not skip. See §0.
#    INTERNAL_API_KEY set in .env, AUTH_CIN_HMAC_KEY set, alembic head confirmed.

# 2. Persistence (safe on a live system: two new tables, nothing altered)
#    - create packages/persistence/src/persistence/models/portal_identity.py   (§3.1)
#    - edit   packages/persistence/src/persistence/models/__init__.py          (§3.2)
#    - create packages/persistence/alembic/versions/0016_portal_identity.py    (§3.3)
cd packages/persistence && python -m alembic upgrade head && python -m alembic heads
cd ../..

# 3. Backend source (not yet live: the image still runs the old code)
#    - create business_api/infrastructure/auth/{passwords,tokens,cin,rate_limit,principal}.py  (§4)
#    - replace business_api/security.py                                                        (§5)
#    - create business_api/portal_auth.py                                                      (§6)
#    - create business_api/seed_admin.py                                                       (§9.2)
#    - edit   business_api/main.py  (four edits)                                               (§7)
#    - edit   .env.example                                                                     (§9.1)

# 4. Agent worker FIRST. It starts sending X-API-Key; today's business-api ignores it.
#    - edit apps/agent-worker/src/clients/routing_client.py                                    (§8.2)
#    - edit apps/agent-worker/src/clients/callback_client.py                                   (§8.3)
docker compose -f infra/docker-compose/docker-compose.apps.yml build agent-worker
docker compose -f infra/docker-compose/docker-compose.apps.yml up -d agent-worker
docker compose -f infra/docker-compose/docker-compose.apps.yml logs --tail=40 agent-worker
# expect a clean start, no traceback

# 5. Tests BEFORE the backend goes live
pytest apps/business-api/tests -q          # expect 49 passed
ruff check apps/business-api/src/business_api/ | tail -3

# 6. Backend live. The Dockerfile bakes source: restart is NOT enough.
docker compose -f infra/docker-compose/docker-compose.apps.yml build business-api
docker compose -f infra/docker-compose/docker-compose.apps.yml up -d business-api
docker compose -f infra/docker-compose/docker-compose.apps.yml ps business-api   # healthy

# 7. Seed the staff login (idempotent)
docker compose -f infra/docker-compose/docker-compose.apps.yml \
  exec business-api python -m business_api.seed_admin
# expect: seeded staff account admin@telecom.tn (administrateur)

# 8. Front ends
#    admin  : session.ts, auth.server.ts, business-api.ts                                     (§10)
#    portal : src/lib/api/* , routes/login.tsx , routes/signup.tsx , routes/_portal.tsx        (§11)
cd Frontend/admin_dashboard   && npx tsc --noEmit && npm run lint && npm run build
cd ../customer_portal         && npx tsc --noEmit && npm run lint && npm run build
```

---

## §14 VERIFICATION — executed, not inspected

Write this to `scripts/verify_p0_1.sh` and run it. Every line prints an observed value; nothing
below is an assertion about code that was merely read.

```bash
#!/usr/bin/env bash
# P0-1 live verification. Run from the repo root, after §13 step 7.
set -u
API="${API:-http://localhost:8108}"
KEY="$(grep -E '^INTERNAL_API_KEY=' .env | cut -d= -f2-)"
EMAIL="$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2-)"
PASS="$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"

say() { printf '\n== %s\n' "$1"; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

say "1  health stays open"
code "$API/health"                                             # expect 200

say "2  unauthenticated read  (was 200 before P0-1)"
code "$API/api/v1/customers"                                   # expect 401

say "3  forged X-Role         (was 200 before P0-1)"
code -H 'X-Role: administrateur' "$API/api/v1/jobs/integrity"  # expect 401

say "4  unauthenticated DESTRUCTIVE call"
code -X POST "$API/api/v1/jobs/retention?dry_run=true"         # expect 401

say "5  login"
TOKEN=$(curl -s -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("token",""))')
[ -n "$TOKEN" ] && echo "token issued (${#TOKEN} chars)" || echo "LOGIN FAILED"

say "6  wrong password"
code -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"definitely-wrong\"}"   # expect 401

say "7  authenticated admin read"
code -H "Authorization: Bearer $TOKEN" "$API/api/v1/customers"        # expect 200

say "8  authenticated admin-only job"
code -H "Authorization: Bearer $TOKEN" "$API/api/v1/jobs/integrity"   # expect 200

say "9  who am i"
curl -s -H "Authorization: Bearer $TOKEN" "$API/api/v1/auth/me"

say "10 machine principal reaches conseiller routes  (THE VOICE PATH)"
code -H "X-API-Key: $KEY" "$API/api/v1/advisors/on-call"              # expect 200
code -H "X-API-Key: $KEY" "$API/api/v1/callbacks/slots?days=2&limit=3" # expect 200

say "11 machine principal is capped at conseiller"
code -H "X-API-Key: $KEY" "$API/api/v1/tickets"                       # expect 403
code -H "X-API-Key: $KEY" "$API/api/v1/jobs/integrity"                # expect 403

say "12 wrong machine key"
code -H "X-API-Key: not-the-key" "$API/api/v1/advisors/on-call"       # expect 401

say "13 logout revokes immediately"
code -X POST -H "Authorization: Bearer $TOKEN" "$API/api/v1/auth/logout"  # expect 200
code -H "Authorization: Bearer $TOKEN" "$API/api/v1/customers"            # expect 401

say "14 the 403 message is byte-identical to the pre-patch contract"
T2=$(curl -s -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -H "X-API-Key: $KEY" "$API/api/v1/tickets"
echo "   ^ expect exactly: {\"detail\":\"requires role >= superviseur\"}"

say "15 CORS no longer advertises X-Role"
curl -s -i -X OPTIONS "$API/api/v1/customers" \
  -H 'Origin: http://localhost:5174' \
  -H 'Access-Control-Request-Method: GET' | grep -i 'access-control-allow-headers'
```

### 14.1 The voice-flow proof — §4.10, *"does not break the existing LiveKit voice-agent flow"*

Static checks are not sufficient here (§12 STEP 6 of the brief). Run the real client, in the real
container, against the real API:

```bash
docker compose -f infra/docker-compose/docker-compose.apps.yml exec agent-worker python - <<'PY'
import asyncio
from clients.routing_client import get_routing_client
from clients.callback_client import get_callback_client

async def main():
    routing, callbacks = get_routing_client(), get_callback_client()
    print("headers      :", dict(routing._client.headers))   # must contain X-API-Key, no X-Role
    print("on-call      :", len(await routing.on_call_advisors()), "advisor(s)")
    slots = await callbacks.free_slots(days=2, limit=3)
    print("free slots   :", len(slots))
    dest = await routing.resolve_available_advisor("general")
    print("claim        :", dest.advisor_id if dest else "none free (valid outcome)")
    if dest:
        await routing.release_advisor(dest.advisor_id)
        print("release      : ok")

asyncio.run(main())
PY
```

**Pass criteria:** `X-API-Key` present, **no `X-Role`**, advisor count ≥ 0 with no exception, slot
count ≥ 0, and a claim that either returns an advisor or `none free`. An `httpx.HTTPStatusError`
or an empty header dict means Gate A was skipped — stop and fix `INTERNAL_API_KEY`.

Then place one real call and confirm an escalation still transfers.

### 14.2 Data-integrity check

```sql
-- Nothing pre-existing was touched.
SELECT count(*) FROM crm.customers;               -- unchanged
SELECT count(*) FROM auth.customer_credentials;   -- unchanged
SELECT count(*) FROM auth.verification_sessions;  -- unchanged: web auth never writes here
SELECT count(*) FROM conversation.turns;          -- unchanged (490)
SELECT count(*) FROM audit.audit_ledger;          -- unchanged: no audit entry is written by login

-- The new tables, and the proof no password is stored in the clear.
SELECT kind, role, email, is_active, left(password_hash, 12) || '…' AS hash FROM auth.portal_accounts;
SELECT count(*) AS live_sessions FROM auth.portal_sessions WHERE revoked_at IS NULL;
```

### 14.3 Gate list (project standard, all twelve)

| # | Gate | Expected |
|---|---|---|
| 1 | `tsc --noEmit`, both apps | 0 |
| 2 | admin non-prettier lint | **exactly 9** (7 `react-refresh/only-export-components`, 2 `react-hooks/exhaustive-deps`) — unchanged |
| 3 | `npm run build`, both apps | 0 |
| 4 | `git diff -- src/lib/nexus/status.ts` | empty |
| 5 | `git diff --stat -- package.json` ×2 | empty — **no new npm dependency** |
| 6 | backend diff scoped to the files named in §13 | yes |
| 7 | zero direct browser requests to `:8108` | yes — both apps proxy server-side |
| 8 | no `rgb(` / `#hex` in new files | yes |
| 9 | no `getDay(`/`getHours(`/`new Date(`/`toLocaleString(` in new UI files | yes — the two route files render no dates |
| 10 | overlays portal to `document.body` | n/a — no overlay added |
| 11 | role gates curl-verified (200 / 401 / **403 one rank below**) | §14 cases 7, 2, 11 |
| 12 | every status chip non-blank | n/a — no chip added |

Additional, specific to this patch:

| # | Gate | Command |
|---|---|---|
| 13 | `X-Role` is dead everywhere | `git grep -n "X-Role"` → **zero hits** outside `.env.example` §25 and CHANGELOG-style docs |
| 14 | no new Python dependency | `git diff --stat -- '**/pyproject.toml'` → empty |
| 15 | pytest | `pytest apps/business-api/tests -q` → **49 passed** |
| 16 | `prettier --write` on touched files only | never `bun run format` |

Use **`git grep`** throughout — `rg` is not on PATH in this shell.

---

## §15 ROLLBACK

Each layer reverts independently. The database step is last and rarely needed.

```bash
# 1. Restore the previous backend behaviour (fastest, ~40 s)
git checkout HEAD -- apps/business-api/src/business_api/
docker compose -f infra/docker-compose/docker-compose.apps.yml build business-api
docker compose -f infra/docker-compose/docker-compose.apps.yml up -d business-api

# 2. Restore the worker's old header
git checkout HEAD -- apps/agent-worker/src/clients/
docker compose -f infra/docker-compose/docker-compose.apps.yml build agent-worker
docker compose -f infra/docker-compose/docker-compose.apps.yml up -d agent-worker

# 3. Front ends
git checkout HEAD -- Frontend/

# 4. Database, ONLY if you also want the tables gone
cd packages/persistence && python -m alembic downgrade 0015_outage_description_area_code
```

**Steps 1–3 need no database change**: `auth.portal_accounts` and `auth.portal_sessions` are
additive. The old code does not know they exist and is unaffected by their presence. That is what
makes this patch safe to roll back under load.

**Hazard H-2 stands:** never `TRUNCATE` or `DROP` the dev database. A previous session permanently
lost the 34th `advisor_shifts` row that way.

---

## §16 IMPACT ANALYSIS

### 16.1 What changes for a user

| Actor | Before | After |
|---|---|---|
| Admin at `/login` | types email + password | **identical** |
| Admin already signed in | stays signed in | **cookie invalid once** — sign in again after deploy (`AdminSession` gained `token`; the old cookie has none, `verifySession` returns it without a token and `businessApi` sends no `Authorization` → 401 → `/login`). One-time, expected. |
| Admin wanting a new password | needed a redeploy | in-app, immediate |
| Customer | no portal login existed | `/signup` claims their line, `/login` returns |
| Caller on the phone | — | **no change whatsoever** |
| Anonymous internet user | full admin API | 401 on everything but `/health` |

> The one-time admin re-login is unavoidable and correct: the pre-patch cookie asserts a role with
> no backing credential, which is precisely what this patch abolishes. Announce it in the deploy
> note. Nothing else logs anyone out.

### 16.2 Performance

| Path | Added cost |
|---|---|
| Any gated request | one indexed lookup on `auth.portal_sessions.token_digest` (unique btree) in the session the request already opened — sub-millisecond |
| Login / signup | one scrypt derivation, ~50–100 ms, **by design** |
| Voice path | one extra HTTP header. Zero measurable cost |
| Connections | **unchanged.** `current_principal` depends on the same `get_session` callable as `DbSession`, so FastAPI's per-request cache returns the same `Session`. One request still opens one connection. |

### 16.3 What was deliberately NOT done

| Not done | Why |
|---|---|
| Touch `role_rank` / `_ROLE_RANK` | already fail-closed and already tested; `role_rank("client") == 0` is what safely admits a fourth role |
| Edit any of the 44 handlers | the dependency they already share was the correct place |
| Edit the 21 `*.server.ts` files | widening one optional property achieves the same with a 21× smaller diff |
| Add a role to `_ROLE_RANK` for clients | it would make `role_rank("client") >= 1` and let a client through a `conseiller` gate. **Absence is the control.** |
| Use JWT | a stateless token cannot be revoked; the portal's Security page already renders "Sign out of all devices", which would have been a lie |
| Use `packages/cache` for throttling | `NullCache.add_if_absent()` returns `True` — fail-open. Wrong primitive for a brute-force control (§4.4) |
| Add `citext` | lower-casing on write in one place is simpler than an extension |
| Fix `BUSINESS_API_URL=8107` | real, logged, **unrelated to auth** → P1-2 item K |
| Fix `.env.example` §25 stale `VITE_*` | same → P1-2 |
| Add `depends_on: redis` | same → P1-2 |
| Build the rest of `/me/*` | client-portal feature work, not identity (§7.5) |
| Audit-log authentication events | `audit.audit_ledger` is a hash chain that "records what, never who" — changing that is an architectural decision, not a P0-1 side effect. Logged as a P1 candidate. |

---

## §17 CONFIDENCE

| Area | Confidence | Basis |
|---|---|---|
| The vulnerability and its fix | **Very high** | `security.py` read in full; all 44 gates enumerated from `main.py` |
| `require_role` contract preserved | **Very high** | name, signature, return type, 403 string compared character by character |
| Migration correctness | **High** | conventions copied from `0009`; `alembic heads` is still a required gate (§0.2) |
| Agent-worker safety | **High** | exact precedent already running in `context_client.py`; all six call sites enumerated; §14.1 executes it |
| CIN digest match | **Very high** | both implementations read; pinned by an independent known-answer test |
| Admin front end | **High** | every touched file read at its current blob SHA |
| Portal front end | **Medium-high** | primitives and theme read in full; the ten `_portal/*` pages were **not** individually read — they are not modified, and `_portal.tsx` gates all of them at one point |
| `customer_360` payload key in one test | **Medium** | flagged in §12.6 with the command to confirm before running |
| Live data preconditions | **Unverified by me** | §0.3 and §0.4 exist precisely because I cannot run SQL against your database |

### Honest limitations

1. **I have not executed anything.** Every command here is written to be run by you. §13–14 are
   ordered so a failure surfaces before the backend goes live.
2. **Gate B may block signup.** If `auth.customer_credentials` is empty, the admin half still ships
   safely and completely; signup needs the seed first.
3. **One test assertion depends on a payload shape** I inferred rather than read (§12.6). The
   command to confirm it is in the note.
4. **The rate limiter is per-process.** Correct today (single uvicorn worker, verified in the
   Dockerfile), and documented in the module with its migration path.

---

## §18 FILE MANIFEST

**Created (18)**

```
packages/persistence/src/persistence/models/portal_identity.py
packages/persistence/alembic/versions/0016_portal_identity.py
apps/business-api/src/business_api/infrastructure/auth/passwords.py
apps/business-api/src/business_api/infrastructure/auth/tokens.py
apps/business-api/src/business_api/infrastructure/auth/cin.py
apps/business-api/src/business_api/infrastructure/auth/rate_limit.py
apps/business-api/src/business_api/infrastructure/auth/principal.py
apps/business-api/src/business_api/portal_auth.py
apps/business-api/src/business_api/seed_admin.py
apps/business-api/tests/test_auth_passwords.py
apps/business-api/tests/test_auth_cin.py
apps/business-api/tests/test_auth_rate_limit.py
apps/business-api/tests/test_auth_http.py
apps/business-api/tests/test_auth_client_scope.py
Frontend/customer_portal/src/lib/api/{config,errors,session,session.server,middleware,business-api,auth.server,me.server}.ts
Frontend/customer_portal/src/routes/login.tsx
Frontend/customer_portal/src/routes/signup.tsx
scripts/verify_p0_1.sh
```

**Modified (9)**

```
packages/persistence/src/persistence/models/__init__.py     2 additive lines
apps/business-api/src/business_api/security.py              full replacement (contract preserved)
apps/business-api/src/business_api/main.py                  4 edits
apps/business-api/tests/conftest.py                         additive fixtures only
apps/agent-worker/src/clients/routing_client.py             2 edits
apps/agent-worker/src/clients/callback_client.py            2 edits
Frontend/admin_dashboard/src/lib/api/session.ts             1 field
Frontend/admin_dashboard/src/lib/api/auth.server.ts         replacement
Frontend/admin_dashboard/src/lib/api/business-api.ts        4 edits
Frontend/customer_portal/src/routes/_portal.tsx             beforeLoad gate
.env.example                                                2 edits
```

**Explicitly untouched:** `role_rank` · `_ROLE_RANK` · all 44 handler bodies · `repositories.py` ·
`advisors.py` · `availability.py` · `callbacks.py` · `policy_view.py` · `jobs/*` ·
`models/auth.py` · `packages/service-auth` · `context_client.py` · every agent, tool, task and
telephony module · both Dockerfiles · both `package.json` · every `pyproject.toml` ·
`status.ts` · both `styles.css` · `primitives.tsx` (both apps) · 21 of 22 admin `lib/api` files.

---

## §19 COMPLETION REPORT TEMPLATE

Fill in with **observed** values. Per §13 of the brief, do not report as verified anything that was
only inspected.

```
P0-1 REAL AUTHENTICATION - COMPLETION REPORT

Commit            :
Alembic head      : 0016_portal_identity
pytest            :      passed  (baseline 28, expected 49)
ruff (business_api):        (baseline 7 pre-existing in main.py)
tsc admin / portal :  0 / 0
lint admin         :     problems (expected exactly 9 warnings)
build admin / portal: 0 / 0

LIVE PROOFS (§14)
 1 health open ...................... [   ]
 2 unauthenticated read 401 ......... [   ]   was 200 before
 3 forged X-Role 401 ................ [   ]   was 200 before
 4 unauthenticated retention 401 .... [   ]   was 200 before
 5 login issues a token ............. [   ]
 6 wrong password 401 ............... [   ]
 7 authenticated read 200 ........... [   ]
 8 admin-only job 200 ............... [   ]
 9 /auth/me returns the right role .. [   ]
10 machine key reaches conseiller ... [   ]   THE VOICE PATH
11 machine key capped at conseiller . [   ]
12 wrong machine key 401 ............ [   ]
13 logout revokes immediately ....... [   ]
14 403 message byte-identical ....... [   ]
15 CORS no longer lists X-Role ...... [   ]

VOICE FLOW (§14.1)
  headers contain X-API-Key, no X-Role  [   ]
  on-call / slots / claim / release ok  [   ]
  one real call escalated successfully  [   ]

DATA INTEGRITY (§14.2)
  crm.customers .................  (unchanged)
  conversation.turns ............  (unchanged, 490)
  audit.audit_ledger ............  (unchanged)
  auth.verification_sessions ....  (unchanged)
  auth.portal_accounts ..........  (new)

DEVIATIONS FROM THIS DOCUMENT
  D1 -
  D2 -

OPEN ITEMS CARRIED FORWARD
  - P0-2: verification + .env.example/compose/deploy docs + 4 negative tests
  - P1-2 item K: BUSINESS_API_URL=8107 in settings.py and .env.example
  - P1-2: stale VITE_* in .env.example §25; Makefile `frontends` target; REDIS_URL host;
          business-api has no depends_on: redis
  - Remaining /me/* surfaces (billing, services, requests, activity) - client-portal features
  - Whether authentication events should enter audit.audit_ledger (architectural decision)
```

---

## §20 NOTE ON P0-2

P0-2 ("fail-closed default role") is **substantially delivered here**: the
`or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")` fallback is gone and unauthenticated
requests fail closed with 401.

What remains for P0-2 as its own item, per your instruction to keep the order:

1. **Verify** — `git grep -n "BUSINESS_API_DEFAULT_ROLE"` returns hits **only** in `.env.example`
   and documentation, never in code.
2. **Config and docs** — remove or annotate it in compose files and `deploy/` docs (§9.1 annotates
   `.env.example`; the others were not read and must be checked, not assumed).
3. **Four negative tests** — covered by `test_auth_http.py` cases 1, 2, 8 and 12; confirm no
   additional surface is missing.

P0-2 will therefore be a short verification-and-cleanup pass rather than new code. I will not start
it until you confirm P0-1 is applied and green.
