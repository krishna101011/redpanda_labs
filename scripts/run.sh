#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -x .venv/bin/python ]] || { echo "Python environment missing. Run: bash scripts/setup.sh" >&2; exit 1; }
[[ -f frontend/dist/index.html ]] || { echo "Frontend build missing. Run: bash scripts/setup.sh" >&2; exit 1; }
if [[ -f .run/redpanda.pid ]]; then
  old_pid="$(cat .run/redpanda.pid 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "A recorded RedPanda Labs process appears to be running (PID $old_pid). Use bash scripts/stop.sh first." >&2
    exit 1
  fi
  rm -f .run/redpanda.pid
fi
mkdir -p .run
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export REDPANDA_HOST="127.0.0.1"
export REDPANDA_PORT="${REDPANDA_PORT:-8000}"

.venv/bin/python -c "from app.database import run_migrations; run_migrations()"

echo "RedPanda Labs starting at http://127.0.0.1:${REDPANDA_PORT}"
echo "This is a local application. Keep it bound to 127.0.0.1."
echo "Press Ctrl+C to stop. Persistent user data and Docker workspaces are not deleted."
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$REDPANDA_PORT" --log-level "${REDPANDA_LOG_LEVEL:-info}" &
APP_PID=$!
printf '%s\n' "$APP_PID" > .run/redpanda.pid
cleanup() {
  if kill -0 "$APP_PID" 2>/dev/null; then
    kill -INT "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  rm -f .run/redpanda.pid
}
trap cleanup INT TERM EXIT
set +e
wait "$APP_PID"
STATUS=$?
set -e
rm -f .run/redpanda.pid
trap - INT TERM EXIT
exit "$STATUS"
