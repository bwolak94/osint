#!/bin/bash
set -e

# Run Alembic migrations before starting the server
echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Starting API server..."
exec "$@"
