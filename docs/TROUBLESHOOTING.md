# Troubleshooting (beginner friendly)

## `Docker CLI is missing`

Docker is the tool that creates the isolated training computer in which Bash runs. Install Docker Engine for your Linux Mint version using the official Docker instructions. The setup script does not use `sudo` or change your user groups for you. After installation, check `docker --version` and `docker info`. If `docker info` says permission denied, follow the Docker documentation for your chosen rootless/rootful setup and understand the security implications before changing permissions.

## Docker daemon unavailable

A Docker client can be installed while the background daemon is stopped or unreachable. Check `docker info`. Start your configured daemon using your normal system service management method. If rootless Docker is selected, follow its user-service instructions. Rerun `bash scripts/diagnostics.sh`.

## Python version / virtual environment errors

Run `python3 --version`; RedPanda Labs requires Python 3.11+. A virtual environment lives in `.venv/` and isolates this project's Python packages from system Python. If it is corrupt, stop the app, rename `.venv` for diagnosis, then rerun setup after checking dependencies. Do not use `sudo pip`.

## Node.js or npm missing

Run `node --version` and `npm --version`. This UI build requires Node.js 20+. Install a supported version, return to the project root, and rerun setup.

## Frontend build missing

Run `cd frontend && npm ci && npm run typecheck && npm run build`. A built `frontend/dist/index.html` is required for normal one-origin serving. If npm reports a package resolution error, note the exact package/version and check the committed lockfile instead of deleting it casually.

## Port 8000 already in use

Another service may already be listening on that port. Check `ss -ltnp | grep ':8000'`. Do not kill an unfamiliar process. For a temporary alternate port, run `REDPANDA_PORT=8010 bash scripts/run.sh`; then open `http://127.0.0.1:8010`. Ensure the PID/process matches RedPanda Labs before stopping it.

## Application starts but challenges cannot start

Open Settings & Lab → Diagnostics. Check daemon reachability and whether the `redpanda-labs:0.1.0` image is ready. If the image is missing, after Docker is healthy run `docker build --build-arg LAB_UID="$(id -u)" --tag redpanda-labs:0.1.0 --file lab-image/Dockerfile .` from the project root. Check storage space and image build errors.

## Terminal disconnected

The terminal uses a WebSocket to connect to a Bash PTY inside a Docker container. Ensure the browser is on the localhost URL, the server is running, and Docker reports the challenge container healthy. Check the backend log shown in the terminal window that started `run.sh`. Refresh the browser and reconnect. The logical session is intended to reattach where available, but it has not been tested end-to-end in this build.

## Workspace missing or not owned

Do not manually delete a container/volume and do not prune Docker resources. Run `bash scripts/diagnostics.sh`; check application labels and challenge IDs. The application should refuse to modify a same-named resource if it cannot prove the resource is owned by RedPanda Labs. Preserve volumes before doing manual recovery.

## Invalid AI key or endpoint

AI is optional. Use offline hints while troubleshooting. Check the provider base URL/model; remote endpoints need HTTPS and must provide an OpenAI-compatible chat-completions API. Test connection again. The credential file is `~/.config/redpanda-labs/ai.json`; inspect permissions with `stat -c '%a %n' ~/.config/redpanda-labs/ai.json` and restrict it to the current owner with `chmod 600 ...` if appropriate. Do not paste keys into logs or screenshots.

## AI timeout or rate limit

The provider may be slow, unavailable or rate-limiting. Use offline hints, lower request complexity, or adjust the timeout within the supported range. The core app does not require AI.

## Database migration error

Stop the application before investigating. Make a copy of `~/.local/share/redpanda-labs/` before any repair. Run `bash scripts/diagnostics.sh`, then inspect the exception from the actual migration command. Do not delete the SQLite database as a generic fix; it contains learning records.

## Run tests

`bash scripts/test.sh` reports test failures. A skipped Docker test means the test could not be run, not that the requirement passed. Keep the complete output when asking for debugging help, but remove personal paths or private data first.
