# Stop all containers.
# Run from project root:
#   powershell -ExecutionPolicy Bypass -File scripts\stop_dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "Stopping all containers..."
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" down
Write-Output "Done."