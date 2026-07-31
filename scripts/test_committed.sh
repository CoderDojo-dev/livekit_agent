#!/usr/bin/env bash
# Run the suites against the committed tree only.
#
# Copying the working directory into a container tests the developer's disk, not the branch.
# That is how a broken URL and a correct test coexisted with a green report.
set -euo pipefail

REF="${1:-HEAD}"
PYTHON_BIN="${PYTHON_BIN:-}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [ -z "$PYTHON_BIN" ]; then
  for cand in python.exe python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      PYTHON_BIN="$cand"
      break
    fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "No Python interpreter found (set PYTHON_BIN explicitly)." >&2
  exit 1
fi
echo "Python interpreter: $PYTHON_BIN"

git archive "$REF" | tar -x -C "$WORKDIR"
echo "Testing $(git rev-parse --short "$REF") from a clean export in $WORKDIR"

cd "$WORKDIR"

# Per-package source dirs (each app keeps its code in src/). Tests import the packages by name.
export PYTHONPATH="$PWD/apps/business-api/src:$PWD/apps/agent-worker/src:$PWD/services/notification-service/src:$PWD/packages/persistence/src:$PWD/packages/service-auth/src:$PWD/packages/audit-trail/src:$PWD/packages/domain-core/src:$PWD/packages/pii-shield/src:$PWD/packages/observability-kit/src:$PWD/packages/object-storage/src:$PWD/packages/notification-client/src"

"$PYTHON_BIN" -m pytest apps/business-api/tests/ -q
"$PYTHON_BIN" -m pytest apps/agent-worker/tests/ -q
"$PYTHON_BIN" -m pytest services/notification-service/tests/ -q
