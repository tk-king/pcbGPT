#!/usr/bin/env bash
#
# Smoke test for the PCBGPT docker services.
# Verifies a service responds 200:
#   backend:  HTTP /docs (FastAPI OpenAPI docs)
#   frontend: HTTP /     (Vite dev server index)
#
# Usage: scripts/docker_smoke_test.sh [backend_url] [frontend_url]
# Env:   SMOKE_TARGET    backend | frontend | both   (default: both)
#        SMOKE_WAIT_MAX  seconds to wait per endpoint (default: 180)

set -euo pipefail

SMOKE_TARGET="${SMOKE_TARGET:-both}"
BACKEND_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost:5173}"
WAIT_MAX="${SMOKE_WAIT_MAX:-180}"

wait_for_200() {
  local url="$1"
  local deadline
  local code=""
  deadline=$(( $(date +%s) + WAIT_MAX ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || true)
    if [ "$code" = "200" ]; then
      echo "OK: GET $url -> 200"
      return 0
    fi
    sleep 3
  done
  echo "FAILED: GET $url never returned 200 (last: ${code:-no response})" >&2
  return 1
}

case "$SMOKE_TARGET" in
  backend)
    wait_for_200 "$BACKEND_URL/docs"
    ;;
  frontend)
    wait_for_200 "$FRONTEND_URL"
    ;;
  both)
    wait_for_200 "$BACKEND_URL/docs"
    wait_for_200 "$FRONTEND_URL"
    ;;
  *)
    echo "ERROR: SMOKE_TARGET must be 'backend', 'frontend' or 'both' (got '$SMOKE_TARGET')" >&2
    exit 2
    ;;
esac

echo "Smoke test passed ($SMOKE_TARGET)."