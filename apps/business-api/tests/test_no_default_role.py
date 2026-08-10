"""P0-2 regression guard: no role may be obtained from the environment.

Until P0-1, business_api.security resolved a caller's role as

    role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")

so an anonymous request arrived as a full administrator. P0-1 deleted that expression and P0-2
deleted the variable from every template and deployment artefact. This module fails the build if
anyone reintroduces an environment-sourced role default anywhere in the business-api source tree.

It is a static source assertion on purpose: it needs no database, no container and no network, so
it runs in CI on every push regardless of what infrastructure is available.
"""

from __future__ import annotations

from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "business_api"

# Substrings that would indicate a role being read from the environment.
_FORBIDDEN = (
    "BUSINESS_API_DEFAULT_ROLE",
    "DEFAULT_ROLE",
)


def _python_sources() -> list[Path]:
    return sorted(p for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts)


def test_source_tree_was_actually_found() -> None:
    """Guard the guard.

    A wrong _SRC would make every assertion below vacuously true — the test would pass while
    checking nothing. Pin two facts that can only hold if the real tree was located.
    """
    sources = _python_sources()
    assert sources, f"no python sources found under {_SRC}"
    names = {p.name for p in sources}
    assert "security.py" in names, f"security.py missing from {_SRC}; _SRC is wrong"
    assert "main.py" in names, f"main.py missing from {_SRC}; _SRC is wrong"


def test_no_environment_sourced_role_default() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for needle in _FORBIDDEN:
            if needle in text:
                offenders.append(f"{path.relative_to(_SRC)} contains {needle!r}")

    assert not offenders, (
        "An environment-sourced role default was reintroduced. Roles must come only from a "
        "principal business-api resolved itself (bearer token or INTERNAL_API_KEY). "
        + "; ".join(offenders)
    )


def test_security_module_does_not_read_the_environment_for_a_role() -> None:
    """Narrow, high-signal check on the module that carried the defect."""
    security = (_SRC / "security.py").read_text(encoding="utf-8")
    assert "os.getenv" not in security, (
        "security.py reads the environment. Role resolution must depend only on the resolved "
        "principal, never on configuration."
    )
    assert "getenv" not in security