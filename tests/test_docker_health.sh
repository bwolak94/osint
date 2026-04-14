#!/usr/bin/env bash
# Health-check script for all docker compose services.
# Usage: ./tests/test_docker_health.sh
# Make executable first: chmod +x tests/test_docker_health.sh

set -euo pipefail

TIMEOUT=120
INTERVAL=5
ELAPSED=0
PASS=0
FAIL=0
RESULTS=""

# Move to project root (one level up from tests/)
cd "$(dirname "$0")/.."

echo "Starting docker compose services..."
docker compose up -d

echo "Waiting up to ${TIMEOUT}s for services to become healthy..."
sleep 10  # give containers a moment to initialise

check_service() {
  local name="$1"
  shift
  if "$@" > /dev/null 2>&1; then
    RESULTS="${RESULTS}\n  [PASS] ${name}"
    PASS=$((PASS + 1))
    return 0
  else
    RESULTS="${RESULTS}\n  [FAIL] ${name}"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

all_healthy() {
  PASS=0
  FAIL=0
  RESULTS=""

  check_service "api      (localhost:8000/health)"          curl -sf http://localhost:8000/health          || true
  check_service "frontend (localhost:5173)"                 curl -sf http://localhost:5173                 || true
  check_service "redis    (redis-cli ping)"                 docker compose exec -T redis redis-cli ping    || true
  check_service "postgres (pg_isready)"                     docker compose exec -T postgres pg_isready     || true
  check_service "neo4j    (localhost:7474)"                 curl -sf http://localhost:7474                 || true
  check_service "minio    (localhost:9000/minio/health/live)" curl -sf http://localhost:9000/minio/health/live || true

  [ "$FAIL" -eq 0 ]
}

# Poll until all services are healthy or timeout is reached
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  if all_healthy; then
    echo ""
    echo "All services healthy after ${ELAPSED}s:"
    echo -e "$RESULTS"
    echo ""
    echo "Result: ${PASS} passed, ${FAIL} failed"
    exit 0
  fi
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

# Final report on timeout
echo ""
echo "Timed out after ${TIMEOUT}s. Service status:"
echo -e "$RESULTS"
echo ""
echo "Result: ${PASS} passed, ${FAIL} failed"
exit 1
