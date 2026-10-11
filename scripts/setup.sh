#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/backend/requirements.txt" || ! -f "$ROOT/frontend/package.json" ]]; then
  echo "Run this script from the extracted redpanda-labs project folder." >&2
  exit 2
fi

fail() { echo "SETUP BLOCKED: $*" >&2; exit 1; }
version_at_least() {
  local current="$1" required="$2"
  [[ "$(printf '%s\n%s\n' "$required" "$current" | sort -V | head -n1)" == "$required" ]]
}

OS_NAME="$(uname -s)"
ARCH="$(uname -m)"
[[ "$OS_NAME" == "Linux" ]] || fail "This first release targets Linux. Detected: $OS_NAME."
echo "RedPanda Labs setup"
echo "  OS/architecture: $OS_NAME / $ARCH"

command -v python3 >/dev/null 2>&1 || fail "Python 3.11+ is required. Install it with your distribution's package manager, then rerun this script. This script does not use sudo or install system packages."
PYTHON="$(command -v python3)"
PYTHON_VERSION="$($PYTHON -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
PYTHON_MAJOR_MINOR="$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
version_at_least "$PYTHON_MAJOR_MINOR" "3.11" || fail "Python 3.11+ is required; found $PYTHON_VERSION."
echo "  Python: $PYTHON_VERSION"

command -v node >/dev/null 2>&1 || fail "Node.js 20+ is required to build the UI. Install Node.js, then rerun this script."
NODE_VERSION="$(node -p 'process.versions.node')"
version_at_least "$NODE_VERSION" "20.0.0" || fail "Node.js 20+ is required; found $NODE_VERSION."
command -v npm >/dev/null 2>&1 || fail "npm is required; install a supported Node.js distribution."
NPM_VERSION="$(npm --version)"
echo "  Node.js/npm: $NODE_VERSION / $NPM_VERSION"

DOCKER_READY=0
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    DOCKER_READY=1
    echo "  Docker daemon: reachable"
  else
    echo "WARNING: Docker CLI is installed, but its daemon is unavailable or access is denied. Continuing with the dashboard/API; practical labs will remain unavailable. No permissions were changed."
  fi
else
  echo "WARNING: Docker CLI is missing. Continuing with dashboard/API setup; practical labs will remain unavailable until Docker is installed and configured."
fi

FREE_KB="$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')"
(( FREE_KB >= 2097152 )) || echo "WARNING: less than about 2 GiB is available on the project filesystem; image building may fail."

mkdir -p "$HOME/.config/redpanda-labs" "$HOME/.local/share/redpanda-labs" "$HOME/.cache/redpanda-labs"
chmod 700 "$HOME/.config/redpanda-labs" "$HOME/.local/share/redpanda-labs" "$HOME/.cache/redpanda-labs" 2>/dev/null || true

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --requirement backend/requirements.txt

if [[ -f frontend/package-lock.json ]]; then
  (cd frontend && npm ci)
else
  echo "WARNING: this source archive has pinned direct frontend dependencies but no generated npm lockfile. The package registry was unreachable during packaging. Running npm install will resolve and create frontend/package-lock.json on this machine."
  (cd frontend && npm install)
fi

# Docker is only needed to prepare the real challenge runtime; the local dashboard/API can
# still be run and explored without it. Never call the image ready unless this succeeds.
if [[ "$DOCKER_READY" == "1" ]]; then
  docker build --build-arg LAB_UID="$(id -u)" --tag redpanda-labs:0.1.0 --file lab-image/Dockerfile .
else
  echo "SKIPPING lab image build because Docker is not ready. Diagnostics will report labs unavailable."
fi
PYTHONPATH="$ROOT/backend" .venv/bin/python -c "from app.database import run_migrations; run_migrations()"
(cd frontend && npm run typecheck && npm run lint && npm test)
(cd frontend && npm run build)

# Validate challenge manifests independently of Docker.
PYTHONPATH="$ROOT/backend" .venv/bin/python - <<'PY'
from app.services.challenges import load_builtins
items = load_builtins()
print(f"Validated {len(items)} built-in challenge manifests and prerequisite graph.")
PY

echo
echo "APPLICATION SETUP COMPLETE. Start RedPanda Labs with: bash scripts/run.sh"
echo "The application will be available at http://127.0.0.1:8000"
if [[ "$DOCKER_READY" != "1" ]]; then
  echo "WARNING: the Bash lab runtime is not ready; practical challenges require Docker. See docs/TROUBLESHOOTING.md."
fi
