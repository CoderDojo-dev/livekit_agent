param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "rebuild", "build", "logs", "status", "health", "help")]
    [string]$Command = "help"
)

$F = "infra/docker-compose/docker-compose.yml"
$A = "infra/docker-compose/docker-compose.apps.yml"

switch ($Command) {
    "help" {
        Write-Host @"
Usage: .\start.ps1 <command>

Commands:
  up        Start all containers (fast, no rebuild)
  down      Stop all containers
  rebuild   Stop, rebuild images, restart (use after code changes)
  build     Rebuild images only (no restart)
  logs      Follow agent-worker + token-service logs
  status    Show container status
  health    Check /health on all services

Examples:
  .\start.ps1 up         # quick start
  .\start.ps1 rebuild    # rebuild after code changes
  .\start.ps1 status     # check running containers
"@
    }
    "up" {
        Write-Host "Starting all containers (infra + apps)..." -ForegroundColor Cyan
        docker compose -f $F -f $A up -d
    }
    "down" {
        Write-Host "Stopping all containers..." -ForegroundColor Yellow
        docker compose -f $F -f $A --profile self-hosted-livekit down
    }
    "rebuild" {
        Write-Host "Stopping containers..." -ForegroundColor Yellow
        docker compose -f $F -f $A --profile self-hosted-livekit down
        Write-Host "Rebuilding images and starting containers..." -ForegroundColor Cyan
        docker compose -f $F -f $A up -d --build
        Write-Host "Done. Run '.\start.ps1 status' to verify." -ForegroundColor Green
    }
    "build" {
        Write-Host "Rebuilding all images (no restart)..." -ForegroundColor Cyan
        docker compose -f $F -f $A build
        Write-Host "Build complete. Run '.\start.ps1 up' to start." -ForegroundColor Green
    }
    "logs" {
        docker compose -f $F -f $A logs -f --tail=120 token-service agent-worker
    }
    "status" {
        docker compose -f $F -f $A ps
    }
    "health" {
        Write-Host "Checking service health endpoints..." -ForegroundColor Cyan
        $services = @(
            @{Name="context-service"; Port=8101},
            @{Name="knowledge-service"; Port=8102},
            @{Name="decision-service"; Port=8103},
            @{Name="policy-service"; Port=8104},
            @{Name="execution-service"; Port=8105},
            @{Name="notification-service"; Port=8106},
            @{Name="token-service"; Port=8107},
            @{Name="business-api"; Port=8108}
        )
        $allHealthy = $true
        foreach ($svc in $services) {
            try {
                $resp = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)/health" -Method Get -TimeoutSec 5
                Write-Host "  OK $($svc.Name) ($($svc.Port))" -ForegroundColor Green
            } catch {
                Write-Host "  FAIL $($svc.Name) ($($svc.Port))" -ForegroundColor Red
                $allHealthy = $false
            }
        }
        if ($allHealthy) { Write-Host "All services healthy!" -ForegroundColor Green }
    }
}
