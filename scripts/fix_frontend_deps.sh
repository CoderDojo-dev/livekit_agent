#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for app in apps/client-widget apps/supervisor-dashboard; do
  echo "==> Reinstalling ${app}"
  cd "${ROOT_DIR}/${app}"
  rm -rf node_modules
  npm ci
done

echo "==> Frontend dependencies are ready for this Linux/WSL environment."
