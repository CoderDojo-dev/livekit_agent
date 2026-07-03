# Install all platform packages, services, MCPs, and tools in the correct order.
# Run once from the project root (with .venv activated):
#   .\.venv\Scripts\Activate.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Installing shared packages =========="
$packages = @(
    "domain-core", "persistence", "audit-trail", "pii-shield",
    "observability-kit", "service-auth", "cache", "object-storage",
    "notification-client", "integration-adapters"
)
foreach ($pkg in $packages) {
    Write-Output "  packages/$pkg..."
    pip install -e "$root\packages\$pkg" --quiet
}

Write-Output "========== Installing services =========="
$services = @(
    "services\context-service", "services\knowledge-service",
    "services\decision-service", "services\policy-service",
    "services\execution-service", "services\notification-service",
    "apps\token-service", "apps\business-api"
)
foreach ($svc in $services) {
    Write-Output "  $svc..."
    pip install -e "$root\$svc" --quiet
}

Write-Output "========== Installing MCP servers =========="
$mcps = @(
    "mcp-servers\ai-knowledge-rag", "mcp-servers\ticketing-glpi",
    "mcp-servers\messaging-gateway"
)
foreach ($mcp in $mcps) {
    Write-Output "  $mcp..."
    pip install -e "$root\$mcp" --quiet
}

Write-Output "========== Installing agent-worker =========="
pip install -e "$root\apps\agent-worker" --quiet

Write-Output "========== Installing honcho (process manager) =========="
pip install honcho --quiet

Write-Output "========== Frontends (npm install) =========="
Push-Location "$root\apps\supervisor-dashboard"
npm install
Pop-Location
Push-Location "$root\apps\client-widget"
npm install
Pop-Location

Write-Output "`nAll packages installed. Next steps:"
Write-Output "  1. Ensure Docker is running"
Write-Output "  2. Run:  powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1"
Write-Output "  3. After startup, run:  python scripts\health_check.py"