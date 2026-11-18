#!/bin/sh
set -e
echo "Running migrations..."
alembic upgrade head
echo "Seeding reference data..."
if [ "${SEED_DEMO:-false}" = "true" ]; then python -m app.seed --demo; else python -m app.seed; fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' ${UVICORN_EXTRA:-}
