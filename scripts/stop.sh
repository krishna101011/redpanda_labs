#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE="$ROOT/.run/redpanda.pid"
if [[ ! -f "$PIDFILE" ]]; then
  echo "No RedPanda Labs run-script PID file was found. If the app is running in the foreground, press Ctrl+C in that terminal."
  exit 0
fi
PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [[ ! "$PID" =~ ^[0-9]+$ ]]; then
  echo "PID file is invalid; removing only the stale project PID file."
  rm -f "$PIDFILE"
  exit 0
fi
if ! kill -0 "$PID" 2>/dev/null; then
  echo "Recorded process is already stopped."
  rm -f "$PIDFILE"
  exit 0
fi
CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
if [[ "$CMDLINE" != *"uvicorn app.main:app"* ]]; then
  echo "Refusing to signal PID $PID because it does not look like the RedPanda Labs server." >&2
  exit 1
fi
kill -INT "$PID"
for _ in {1..30}; do
  if ! kill -0 "$PID" 2>/dev/null; then break; fi
  sleep 0.2
done
if kill -0 "$PID" 2>/dev/null; then
  echo "Server did not stop promptly. Stop it from its owning terminal with Ctrl+C." >&2
  exit 1
fi
rm -f "$PIDFILE"
echo "RedPanda Labs server stopped. Workspaces and saved data were preserved."
