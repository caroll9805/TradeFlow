# TradeFlow - build, start and verify the whole stack on Windows (PowerShell 5.1+/7, Docker Desktop).
# Usage (from the TradeFlow folder):  powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
# Every step's full output is saved in .\logs\<step>.log
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path logs | Out-Null

function Step([string]$name, [string]$command) {
  # cmd.exe redirection keeps docker's stderr progress out of PowerShell error records and writes plain text logs
  cmd /c "$command > logs\$name.log 2>&1"
  $code = $LASTEXITCODE
  Get-Content "logs\$name.log" -Tail 25 | Out-Host
  return $code
}

Write-Host "== 1/5 Checking Docker ==" -ForegroundColor Cyan
$tries = 0
do {
  cmd /c "docker info > logs\docker-info.log 2>&1"
  if ($LASTEXITCODE -eq 0) { break }
  $tries++; Write-Host "Waiting for the Docker engine (start Docker Desktop if it is not running)..."; Start-Sleep -Seconds 10
} while ($tries -lt 18)
if ($LASTEXITCODE -ne 0) { Write-Host "Docker engine is not running. Start Docker Desktop, wait for 'Engine running', re-run." -ForegroundColor Red; exit 1 }
docker compose version

Write-Host "== 2/5 Preparing .env ==" -ForegroundColor Cyan
if (-not (Test-Path .env)) {
  function New-Secret([int]$n) { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $n | ForEach-Object { [char]$_ }) }
  (Get-Content .env.example -Raw) `
    -replace 'POSTGRES_PASSWORD=.*', ("POSTGRES_PASSWORD=" + (New-Secret 24)) `
    -replace 'JWT_SECRET=.*', ("JWT_SECRET=" + (New-Secret 48)) |
    Set-Content -NoNewline -Encoding ascii .env
  Write-Host "Created .env with random POSTGRES_PASSWORD and JWT_SECRET (SEED_DEMO=true)."
} else { Write-Host ".env already exists - kept." }
# Older .env files used the reserved ".local" domain, which e-mail validation rejects.
$envText = Get-Content .env -Raw
if ($envText -match "tradeflow\.local") { ($envText -replace "admin@tradeflow\.local", "admin@example.com") | Set-Content -NoNewline -Encoding ascii .env; Write-Host "Updated BOOTSTRAP_ADMIN_EMAIL in .env." }

Write-Host "== 3/5 Building images: installs all Python (pip) and npm dependencies inside the containers ==" -ForegroundColor Cyan
Write-Host "   First run downloads ~1-2 GB and can take 5-15 minutes."
# Build one image at a time (shares slow bandwidth) and retry: BuildKit cache mounts keep finished downloads.
foreach ($svc in @("backend", "frontend")) {
  $ok = $false
  for ($attempt = 1; $attempt -le 3 -and -not $ok; $attempt++) {
    Write-Host "Building $svc (attempt $attempt of 3)..."
    $ok = ((Step "build-$svc" "docker compose --progress plain build $svc") -eq 0)
    if (-not $ok) { Write-Host "Build of $svc failed (often a network timeout) - retrying..." -ForegroundColor Yellow; Start-Sleep -Seconds 10 }
  }
  if (-not $ok) { Write-Host "Build of $svc failed 3 times - see logs\build-$svc.log and docs\TROUBLESHOOTING.md" -ForegroundColor Red; exit 1 }
}

Write-Host "== 4/5 Starting services (db, backend: migrations + seed, worker, frontend) ==" -ForegroundColor Cyan
if ((Step "up" "docker compose up -d --no-build") -ne 0) { Write-Host "Start failed - see logs\up.log" -ForegroundColor Red; exit 1 }
$deadline = (Get-Date).AddMinutes(5)
do {
  Start-Sleep -Seconds 5
  $id = docker compose ps -q backend
  $state = if ($id) { docker inspect --format "{{.State.Health.Status}}" $id } else { "missing" }
  Write-Host "backend health: $state"
} until ($state -eq "healthy" -or (Get-Date) -gt $deadline)
cmd /c "docker compose logs --no-color > logs\services.log 2>&1"
if ($state -ne "healthy") { Write-Host "Backend did not become healthy - see logs\services.log" -ForegroundColor Red; docker compose ps; exit 1 }

Write-Host "== 5/5 End-to-end smoke test through the frontend proxy ==" -ForegroundColor Cyan
$smoke = Step "smoke" "docker compose exec -T backend python -m app.smoke --base http://frontend"
cmd /c "docker compose ps > logs\ps.log 2>&1"
if ($smoke -eq 0) {
  Write-Host "`nTradeFlow is running:  http://localhost:8080   (API docs: http://localhost:8000/api/docs)" -ForegroundColor Green
  Write-Host "Demo logins: buyer@ / supplier@ / data@ / admin@demo.example.com  password Demo12345!"
} else { Write-Host "Smoke test reported failures - see logs\smoke.log" -ForegroundColor Yellow; exit 1 }
