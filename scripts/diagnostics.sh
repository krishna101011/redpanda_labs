#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
section() { printf '\n\033[1m%s\033[0m\n' "$1"; }
show_version() { if command -v "$1" >/dev/null 2>&1; then "$@" 2>&1 | head -n 2; else echo "Not installed"; fi; }
section "System"
uname -a
printf 'Architecture: '; uname -m
printf 'Free disk space: '; df -h "$ROOT" | awk 'NR==2 {print $4 " available of " $2}'
section "Language tools"
show_version python3 --version
show_version node --version
show_version npm --version
section "Docker"
if command -v docker >/dev/null 2>&1; then
  docker --version
  if docker info >/dev/null 2>&1; then
    echo "Daemon: reachable for this user"
    docker info --format 'Server={{.ServerVersion}} SecurityOptions={{json .SecurityOptions}}' 2>/dev/null || true
    docker image inspect redpanda-labs:0.1.0 --format 'Lab image: {{.Id}}' 2>/dev/null || echo "Lab image: missing"
  else
    echo "Daemon: unavailable or access denied; no permission changes attempted"
  fi
else
  echo "Docker CLI: not installed"
fi
section "Project readiness"
[[ -x .venv/bin/python ]] && echo "Python virtual environment: present" || echo "Python virtual environment: missing"
[[ -f frontend/package-lock.json ]] && echo "npm lockfile: present" || echo "npm lockfile: missing"
[[ -d frontend/node_modules ]] && echo "npm dependencies: installed" || echo "npm dependencies: not installed"
[[ -f frontend/dist/index.html ]] && echo "Frontend build: present" || echo "Frontend build: missing"
if [[ -x .venv/bin/python ]]; then
  PYTHONPATH="$ROOT/backend" .venv/bin/python - <<'PY'
try:
    from app.services.challenges import load_builtins
    print(f"Challenge manifests: {len(load_builtins())} valid")
except Exception as exc:
    print(f"Challenge manifests: ERROR ({type(exc).__name__}: {exc})")
PY
fi
for d in "$HOME/.config/redpanda-labs" "$HOME/.local/share/redpanda-labs" "$HOME/.cache/redpanda-labs"; do
  [[ -d "$d" ]] && printf 'Data directory present: %s\n' "$d" || printf 'Data directory missing: %s\n' "$d"
done
if command -v curl >/dev/null 2>&1; then
  if curl --silent --show-error --max-time 1 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then echo "Local app health: responding at 127.0.0.1:8000"; else echo "Local app health: not responding at 127.0.0.1:8000"; fi
fi
section "Tests"
if [[ -x .venv/bin/pytest ]]; then
  echo "Run full available test suite: bash scripts/test.sh"
else
  echo "Backend test runner not installed yet. Run setup after prerequisites are available."
fi
