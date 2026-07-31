# Run the suites against the committed tree only.
#
# Copying the working directory into a container tests the developer's disk, not the branch.
# That is how a broken URL and a correct test coexisted with a green report.
# Canonical validation script for this repository (Windows PowerShell; no WSL/git-bash required).
param([string]$Ref = "HEAD")

$ErrorActionPreference = "Stop"

$work = Join-Path $env:TEMP ("test_committed_" + $PID)
New-Item -ItemType Directory -Path $work | Out-Null
try {
    git archive $Ref -o (Join-Path $work "committed.tar")
    tar -xf (Join-Path $work "committed.tar") -C $work
    $sha = git rev-parse --short $Ref
    Write-Output "Testing $sha from a clean export in $work"

    Push-Location $work
    try {
        $env:PYTHONPATH = @(
            "$work/apps/business-api/src",
            "$work/apps/agent-worker/src",
            "$work/services/notification-service/src",
            "$work/services/policy-service/src",
            "$work/packages/persistence/src",
            "$work/packages/service-auth/src",
            "$work/packages/audit-trail/src",
            "$work/packages/domain-core/src",
            "$work/packages/pii-shield/src",
            "$work/packages/observability-kit/src",
            "$work/packages/object-storage/src",
            "$work/packages/notification-client/src"
        ) -join ";"

        # Pin the connection string the same way PYTHONPATH is pinned: the validation chain must
        # not depend on whatever DATABASE_URL the invoking shell happens to carry (a compose
        # hostname instead of localhost would fail the policy suite on a healthy branch). No skip
        # if Postgres is unreachable - a test that disables itself is how defects survive.
        $env:DATABASE_URL = "postgresql+psycopg://telecom:telecom@localhost:5432/telecom"

        python -m pytest apps/business-api/tests/ -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        python -m pytest apps/agent-worker/tests/ -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        python -m pytest services/notification-service/tests/ -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        python -m pytest services/policy-service/tests/ -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
} finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
