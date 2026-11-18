# TradeFlow - run every automated check inside Docker; full output in .\logs
# Usage:  powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1   (rebuilds images from current code first)
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path logs | Out-Null
if (-not (Test-Path .env)) { Write-Host "Run scripts\start.ps1 first (it creates .env)." -ForegroundColor Red; exit 1 }

function Step([string]$name, [string]$command) {
  Write-Host "== $name ==" -ForegroundColor Cyan
  cmd /c "$command > logs\$name.log 2>&1"
  $code = $LASTEXITCODE
  Get-Content "logs\$name.log" -Tail 25 | Out-Host
  if ($code -eq 0) { Write-Host "[$name] OK" -ForegroundColor Green } else { Write-Host "[$name] FAILED (exit $code)" -ForegroundColor Red }
  return $code
}

$results = [ordered]@{}
$results["rebuild"]        = Step "rebuild" "docker compose --progress plain build backend frontend"
$results["restart"]        = Step "restart" "docker compose up -d --no-build --wait --wait-timeout 300"
$results["pytest"]         = Step "pytest" "docker compose run --rm --no-deps backend pytest -v -ra"
$results["migrations"]     = Step "migrations" "docker compose run --rm backend alembic current"
$results["frontend-build"] = Step "frontend-build" "docker compose --progress plain --profile test build frontend-test"
$results["vitest"]         = Step "vitest" "docker compose --profile test run --rm frontend-test"
$results["smoke"]          = Step "smoke" "docker compose exec -T backend python -m app.smoke --base http://frontend"

Write-Host "`n== Summary ==" -ForegroundColor Cyan
$fail = 0
foreach ($k in $results.Keys) { if ($results[$k] -eq 0) { Write-Host "PASS  $k" -ForegroundColor Green } else { $fail++; Write-Host "FAIL  $k" -ForegroundColor Red } }
$results.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } | Set-Content logs\test-summary.txt
if ($fail -gt 0) { exit 1 }
