#!/usr/bin/env bash
set -euo pipefail

MAX_WAIT=120
BASE_URL="${BASE_URL:-http://localhost:8080}"
INTERVAL=5

echo "Waiting for services to be ready (max ${MAX_WAIT}s)..."

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "$BASE_URL/health" > /dev/null 2>&1; then
        echo "Services are ready! (took ${elapsed}s)"
        exit 0
    fi

    echo "  Waiting... (${elapsed}s)"
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

echo "ERROR: Services did not become ready within ${MAX_WAIT}s"
docker compose ps
docker compose logs --tail 20
exit 1
