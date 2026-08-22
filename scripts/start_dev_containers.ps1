# Container-only path: build + run everything via Docker Compose (no honcho).
# Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\start_dev_containers.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Building + starting everything (infra + apps) =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" up -d --build

Write-Output "========== Waiting for postgres =========="
$attempts = 0
while ($attempts -lt 30) {
    $ready = docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres pg_isready -U telecom 2>&1 | Out-String
    if ($ready -match "accepting connections") { break }
    Start-Sleep -Seconds 2
    $attempts++
}

Write-Output "========== Applying migrations =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres sh -c "pg_isready -U telecom"
# Migrations run inside the context-service container:
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" exec -T context-service sh -c "cd /app/packages/persistence && alembic upgrade head && python -m seed.seed_pilot && python -m seed.seed_reference && python -m seed.seed_portal_activity"

Write-Output "`nAll containers running. Health check:"
Write-Output "  python scripts\health_check.py"
Write-Output "  Stop:  docker compose -f infra\docker-compose\docker-compose.yml -f infra\docker-compose\docker-compose.apps.yml down"