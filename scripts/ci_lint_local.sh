#!/usr/bin/env bash
# scripts/ci_lint_local.sh
# Reproduces the "lint" job from CI WITHOUT the "|| true" masking.
set -uo pipefail

echo "==================== RUFF ===================="
ruff check .
RUFF_RC=$?
echo "ruff exit code = $RUFF_RC"

echo "==================== MYPY ===================="
mypy packages/ services/ apps/
MYPY_RC=$?
echo "mypy exit code = $MYPY_RC"

echo "============================================="
echo "RESUME : ruff=$RUFF_RC  mypy=$MYPY_RC"
if [ "$RUFF_RC" -eq 0 ] && [ "$MYPY_RC" -eq 0 ]; then
  echo "Backlog vide : on peut retirer les '|| true' sans casser le CI."
  exit 0
else
  echo "Backlog non vide : corriger AVANT de modifier ci.yml (voir etape 4b)."
  exit 1
fi
