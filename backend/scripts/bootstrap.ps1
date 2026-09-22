<#
.SYNOPSIS
  One-command local setup for the MetrologyAI backend on Windows.

  1. Creates the PostgreSQL database (if missing) and enables PostGIS
  2. Creates/updates the Python virtual environment and installs dependencies
  3. Runs Alembic migrations
  4. Seeds development users and the statutory Schedule II ruleset

.PARAMETER SkipAi
  Skip installing the CPU OCR stack (requirements-ai.txt).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#>
param(
    [switch]$SkipAi,
    [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin",
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgrespassword",
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$DbName = "metrologyai"
)

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

if (-not (Test-Path (Join-Path $PgBin "psql.exe"))) {
    Write-Error "psql.exe not found in '$PgBin'. Install PostgreSQL 16 (winget install PostgreSQL.PostgreSQL.16) and the PostGIS bundle, or pass -PgBin."
}

$env:PGPASSWORD = $PgPassword
$psql = Join-Path $PgBin "psql.exe"

Write-Host "==> Ensuring database '$DbName' exists" -ForegroundColor Cyan
$exists = & $psql -U $PgUser -h $PgHost -p $PgPort -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
if ($exists -ne "1") {
    & $psql -U $PgUser -h $PgHost -p $PgPort -c "CREATE DATABASE $DbName" | Out-Null
}
& $psql -U $PgUser -h $PgHost -p $PgPort -d $DbName -c "CREATE EXTENSION IF NOT EXISTS postgis" | Out-Null

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "==> Creating virtual environment" -ForegroundColor Cyan
    python -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"

Write-Host "==> Installing dependencies" -ForegroundColor Cyan
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt
if (-not $SkipAi) {
    Write-Host "==> Installing CPU OCR stack (PaddleOCR)" -ForegroundColor Cyan
    & $py -m pip install --quiet -r requirements-ai.txt
}

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example" -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
    $secret = & $py -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content ".env") -replace '^JWT_SECRET_KEY=.*$', "JWT_SECRET_KEY=$secret" | Set-Content ".env" -Encoding utf8
    (Get-Content ".env") -replace '^POSTGRES_PASSWORD=.*$', "POSTGRES_PASSWORD=$PgPassword" | Set-Content ".env" -Encoding utf8
}

Write-Host "==> Running migrations" -ForegroundColor Cyan
& $py -m alembic upgrade head

Write-Host "==> Seeding development users and ruleset" -ForegroundColor Cyan
& $py -m app.db.seed_users
& $py -m app.db.seed_rulesets
Write-Host "==> Seeding demo scans through the real pipeline (loads OCR models, ~1 min)" -ForegroundColor Cyan
& $py -m app.db.seed_scans

Write-Host ""
Write-Host "Backend ready. Start it with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
