#!/usr/bin/env bash
# One-command local setup for the MetrologyAI backend on Linux/macOS.
# Requires: python3.10+, a reachable PostgreSQL with the PostGIS extension available.
set -euo pipefail
cd "$(dirname "$0")/.."

PG_USER="${PG_USER:-postgres}"
PG_PASSWORD="${PG_PASSWORD:-postgrespassword}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
DB_NAME="${DB_NAME:-metrologyai}"
SKIP_AI="${SKIP_AI:-0}"

export PGPASSWORD="$PG_PASSWORD"
echo "==> Ensuring database '$DB_NAME' exists"
if [ "$(psql -U "$PG_USER" -h "$PG_HOST" -p "$PG_PORT" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")" != "1" ]; then
  psql -U "$PG_USER" -h "$PG_HOST" -p "$PG_PORT" -c "CREATE DATABASE $DB_NAME"
fi
psql -U "$PG_USER" -h "$PG_HOST" -p "$PG_PORT" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis" >/dev/null

[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python
echo "==> Installing dependencies"
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet -r requirements.txt
if [ "$SKIP_AI" != "1" ]; then
  echo "==> Installing CPU OCR stack (PaddleOCR)"
  $PY -m pip install --quiet -r requirements-ai.txt
fi

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  SECRET=$($PY -c "import secrets; print(secrets.token_urlsafe(48))")
  sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$SECRET|; s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PG_PASSWORD|" .env && rm -f .env.bak
fi

echo "==> Running migrations"
$PY -m alembic upgrade head
echo "==> Seeding development users and ruleset"
$PY -m app.db.seed_users
$PY -m app.db.seed_rulesets
echo "==> Seeding demo scans through the real pipeline (loads OCR models, ~1 min)"
$PY -m app.db.seed_scans

echo
echo "Backend ready. Start it with:  .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
