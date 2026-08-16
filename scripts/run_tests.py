#!/usr/bin/env python3
"""Run the offline test suite across packages/services with the right PYTHONPATH (diagnostic #9)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = "src"

# (dir, extra PYTHONPATH entries relative to the dir, pytest target)
TARGETS = [
    ("packages/audit-trail", ["../persistence/src", "../domain-core/src"], "tests"),
    ("packages/service-auth", [], "tests"),
    ("packages/cache", [], "tests"),
    ("packages/object-storage", [], "tests"),
    ("packages/integration-adapters", ["../domain-core/src", "../service-auth/src"], "tests"),
    ("packages/persistence", [], "tests"),
    ("packages/observability-kit", [], "tests"),
    ("services/context-service", ["../../packages/cache/src", "../../packages/persistence/src", "../../packages/service-auth/src"], "tests"),
    ("services/knowledge-service", ["../../packages/service-auth/src"], "tests"),
    ("services/policy-service", ["../../packages/audit-trail/src", "../../packages/persistence/src", "../../packages/domain-core/src", "../../packages/service-auth/src"], "tests"),
    ("services/execution-service", ["../../packages/integration-adapters/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src", "../../packages/service-auth/src"], "tests"),
    ("services/notification-service", ["../../packages/persistence/src", "../../packages/pii-shield/src", "../../packages/service-auth/src"], "tests"),
    ("mcp-servers/ticketing-glpi", ["../../packages/persistence/src"], "tests"),
    ("apps/business-api", ["../../packages/object-storage/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src"], "tests"),
    # P1-3: the agent-worker suite existed but was run by nothing — not by `make test`, not by CI.
    ("apps/agent-worker", ["../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src", "../../packages/observability-kit/src", "../../packages/object-storage/src", "../../packages/service-auth/src"], "tests"),
    ("apps/token-service", [], "tests"),
    # P1-3: present in CI's loop but missing here — the two inventories had drifted apart.
    # decision-service needs no extra PYTHONPATH: its test imports scorer only (stdlib), empty __init__.
    ("services/decision-service", [], "tests"),
]


def main() -> int:
    failed = []
    for rel, extra, target in TARGETS:
        d = ROOT / rel
        pp = os.pathsep.join([SRC, *extra])
        env = os.environ.copy()
        env["PYTHONPATH"] = pp
        # Keep the other suites hermetic; agent-worker uses @pytest.mark.asyncio, which needs the
        # entry-point-loaded pytest-asyncio plugin (P1-3: without it the async tests fail with an
        # unknown-mark warning instead of running).
        if rel != "apps/agent-worker":
            env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", target],
            cwd=d,
            env=env,
        )
        status = "ok" if result.returncode == 0 else "FAIL"
        print(f"[{status}] {rel}")
        if result.returncode != 0:
            failed.append(rel)
    print("\nAll suites passed." if not failed else f"\nFailed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
