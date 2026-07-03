# Start the entire platform: infra containers + DB setup + all processes via honcho.
# Run from the project root (with .venv activated):
#   .\.venv\Scripts\Activate.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1
#
# Requirements: Docker running, `scripts/install_dev.ps1` completed first.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Starting infrastructure containers =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" up -d

Write-Output "========== Waiting for postgres =========="
$attempts = 0
while ($attempts -lt 30) {
    $ready = docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres pg_isready -U telecom 2>&1 | Out-String
    if ($ready -match "accepting connections") { break }
    Start-Sleep -Seconds 2
    $attempts++
}
if ($attempts -ge 30) {
    Write-Output "WARNING: postgres not ready after 60s — continuing anyway"
}

Write-Output "========== Applying migrations =========="
Push-Location "$root\packages\persistence"
alembic upgrade head
Pop-Location

Write-Output "========== Seeding pilot data =========="
Push-Location "$root\packages\persistence"
python -m seed.seed_pilot
python -m seed.seed_reference
Pop-Location

Write-Output "========== Starting all services via honcho =========="
Write-Output "(Ctrl+C to stop all processes)"
honcho start