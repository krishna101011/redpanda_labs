#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/pytest ]] || { echo "Backend test environment missing. Run bash scripts/setup.sh first." >&2; exit 1; }
[[ -d frontend/node_modules ]] || { echo "Frontend dependencies missing. Run bash scripts/setup.sh first." >&2; exit 1; }
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export REDPANDA_DATA_DIR="${REDPANDA_TEST_DATA_DIR:-$ROOT/.test-data}"
export REDPANDA_CONFIG_DIR="${REDPANDA_TEST_CONFIG_DIR:-$ROOT/.test-config}"
export REDPANDA_CACHE_DIR="${REDPANDA_TEST_CACHE_DIR:-$ROOT/.test-cache}"
mkdir -p "$REDPANDA_DATA_DIR" "$REDPANDA_CONFIG_DIR" "$REDPANDA_CACHE_DIR"
chmod 700 "$REDPANDA_DATA_DIR" "$REDPANDA_CONFIG_DIR" "$REDPANDA_CACHE_DIR" 2>/dev/null || true

echo "== Backend tests =="
.venv/bin/pytest backend/tests -ra

echo "== Frontend typecheck =="
(cd frontend && npm run typecheck)
echo "== Frontend lint =="
(cd frontend && npm run lint)
echo "== Frontend tests =="
(cd frontend && npm test)
echo "All runnable checks completed. Docker integration tests are reported as skipped when Docker is unavailable."
