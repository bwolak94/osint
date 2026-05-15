#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# Database migrations — run before starting the API server.
#
# Multiple replicas starting simultaneously could all run migrations at once.
# Alembic uses a table-level lock on `alembic_version` which prevents corrupt
# state, but concurrent runners each pay the startup latency.  We use a
# PostgreSQL advisory lock (key 20240101) so only one replica runs migrations
# while the others wait, then proceed immediately once the lock is released. (#38)
# ---------------------------------------------------------------------------

echo "[entrypoint] Acquiring migration advisory lock and running database migrations..."

# The advisory lock is acquired in a short-lived psql session.  alembic runs
# inside it; the lock is automatically released when psql exits.
python -c "
import os, subprocess, sys
import psycopg2

dsn = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
if not dsn:
    # Fall back to individual env vars
    host = os.environ.get('POSTGRES_HOST', 'postgres')
    port = os.environ.get('POSTGRES_PORT', '5432')
    user = os.environ.get('POSTGRES_USER', 'osint')
    pw   = os.environ.get('POSTGRES_PASSWORD', 'osint')
    db   = os.environ.get('POSTGRES_DB', 'osint')
    dsn  = f'postgresql://{user}:{pw}@{host}:{port}/{db}'

conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
cur.execute('SELECT pg_advisory_lock(20240101)')
try:
    result = subprocess.run(['alembic', 'upgrade', 'head'], check=True)
finally:
    cur.execute('SELECT pg_advisory_unlock(20240101)')
    conn.close()
" || {
    echo "[entrypoint] psycopg2 advisory lock not available, running migrations without lock"
    alembic upgrade head
}

echo "[entrypoint] Starting API server..."
exec "$@"
