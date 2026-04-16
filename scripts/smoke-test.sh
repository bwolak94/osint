#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
PASSED=0
FAILED=0

check() {
    local url="$1"
    local expected="$2"
    local desc="$3"

    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)

    if [ "$status" = "$expected" ]; then
        echo "  PASS  $desc ($url -> $status)"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL  $desc ($url -> $status, expected $expected)"
        FAILED=$((FAILED + 1))
    fi
}

echo "Running smoke tests against $BASE_URL..."
echo ""

check "$BASE_URL/health" "200" "Health check"
check "$BASE_URL/health/live" "200" "Liveness"
check "$BASE_URL/api/v1/auth/me" "401" "Protected endpoint returns 401"
check "$BASE_URL/" "200" "Frontend served"

echo ""
echo "Results: $PASSED passed, $FAILED failed"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
echo "All smoke tests passed!"
