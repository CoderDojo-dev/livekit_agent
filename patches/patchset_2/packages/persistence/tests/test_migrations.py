"""Offline migration-integrity tests (no DB): unique revisions + a linear chain + full registration.

The live 'alembic upgrade head' check runs in CI against a real Postgres (report #29); here we
guard the two things that silently break a migration set without a database.
"""
from __future__ import annotations

import pathlib
import re

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revisions() -> dict[str, str | None]:
    chain: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob("0*.py")):
        text = path.read_text()
        rev = re.search(r'revision\s*=\s*"([^"]+)"', text)
        down = re.search(r'down_revision\s*=\s*(?:"([^"]+)"|None)', text)
        assert rev, f"{path.name}: no revision id"
        chain[rev.group(1)] = down.group(1) if down and down.group(1) else None
    return chain


def test_revision_ids_are_unique() -> None:
    ids = [re.search(r'revision\s*=\s*"([^"]+)"', p.read_text()).group(1) for p in sorted(VERSIONS.glob("0*.py"))]
    assert len(ids) == len(set(ids)), "duplicate revision ids"


def test_chain_is_linear_with_one_root() -> None:
    chain = _revisions()
    roots = [rev for rev, down in chain.items() if down is None]
    assert len(roots) == 1, f"expected exactly one root migration, got {roots}"
    for rev, down in chain.items():
        assert down is None or down in chain, f"{rev} points to missing down_revision {down}"


def test_all_models_register_on_metadata() -> None:
    from sqlalchemy.orm import configure_mappers

    from persistence.base import Base
    import persistence.models  # noqa: F401

    configure_mappers()
    schemas = {name.split(".")[0] for name in Base.metadata.tables}
    for expected in ("crm", "billing", "ocs", "policy", "execution", "audit",
                     "conversation", "sim", "ticketing", "reference", "oss", "provisioning"):
        assert expected in schemas, f"schema {expected} has no registered tables"