# RedPanda Labs

**A local-first cybersecurity learning workbench for Linux, Bash, Python, networking, and web-security fundamentals.** The interface is React + TypeScript; the API is FastAPI; learning records live in a local SQLite database; and challenge commands are intended to run in Docker lab containers, not in the normal Linux Mint shell.

> **Project status: development build, not release-ready.** The local API/UI, challenge manifests, offline hints, learning records, notebook, authoring flows, backup endpoints, and optional AI adapter are implemented in source. This project was assembled in an environment without Docker, so real-container terminal execution, reset/reconnect semantics, and network isolation have not been verified here. A session-restricted browser gateway for web targets and safe custom script execution are also not implemented. Review [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) before using it.

## What is included

- Fifteen distinct versioned challenge manifests with track/difficulty, prerequisites, starter artifacts, three progressive offline hints, and completion explanations.
- A React workbench with dashboard, learning path, mission catalogue, terminal workspace, notebook, challenge builder, settings, and diagnostics.
- A FastAPI API, SQLAlchemy models, Alembic migration, challenge prerequisite graph validation, progress history, achievements, notes, and separate saved explanations.
- A Docker image definition and managed-workspace code using labelled named volumes, non-root execution, dropped capabilities, resource limits, and no outbound network by default. Challenges that require local services use an isolated internal Docker network. Docker is not a perfect security boundary.
- An xterm.js terminal frontend and a PTY-based `docker exec` session path.
- Offline-first mentor hints and explanations, plus an optional OpenAI-compatible API adapter. API credentials are stored outside the source folder in `~/.config/redpanda-labs/ai.json` with owner-only permissions.
- Separate progress/notes exports, workspace archives, and challenge-pack exports. Imports are size-limited and validated.
- Linux setup, run, stop, diagnostics, and test scripts.

## Requirements

For the full local experience:

- Linux Mint or a compatible Linux distribution.
- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- Docker Engine/CLI with a working daemon for real shell challenges. Rootless Docker is preferred where compatible. The scripts do not silently run `sudo`, change group membership, change firewall rules, or modify Docker configuration.
- Approximately 2 GiB or more free disk space is recommended for dependencies and the training image; actual usage depends on platform and Docker cache.

The dashboard/API can be inspected without starting Docker, but practical shell missions cannot run until Docker and the image are ready.

## Install on Linux Mint

1. Download `redpanda-labs.zip` and extract it.
2. Open the extracted `redpanda-labs` folder in VS Code (`File → Open Folder`).
3. Open VS Code's terminal from **Terminal → New Terminal**. Make sure the terminal is at the project root.
4. Run:

```bash
cd redpanda-labs
bash scripts/setup.sh
```

`setup.sh` checks system dependencies, makes a Python virtual environment, installs the pinned Python requirements and exact direct frontend dependency versions, builds the frontend and (when Docker is ready) lab image, applies database migrations, and checks the manifests. It does not install system packages or change OS security settings for you. **Packaging limitation:** the npm registry was unreachable in the build environment, so this source bundle currently has no committed `frontend/package-lock.json`. The first setup therefore needs npm registry access to resolve transitive packages; generate and commit the lockfile before treating this as a release.

5. Start the application:

```bash
bash scripts/run.sh
```

6. Open **http://127.0.0.1:8000** in a browser. Keep the application on loopback; do not expose it to the LAN or public Internet.
7. To stop it, press **Ctrl+C** in the terminal running it. Alternatively, from a second terminal run `bash scripts/stop.sh`. Stopping the app does **not** remove workspaces or learning records.

### Quick meanings

- `cd redpanda-labs`: enters the project folder.
- `bash scripts/setup.sh`: installs project-level dependencies and prepares the lab image.
- `bash scripts/run.sh`: runs the native Python backend, which serves the built React interface on localhost.
- `bash scripts/stop.sh`: asks the app server launched by `run.sh` to stop without deleting saved data.
- `bash scripts/diagnostics.sh`: prints environment and readiness information without printing secret values.
- `bash scripts/test.sh`: runs backend and frontend test suites available in the environment.

## First launch

On the dashboard, inspect readiness/diagnostics before starting a mission. If Docker is unavailable, the UI/API can still be explored, but a real terminal will not be available. The terminal should display a custom RedPanda prompt when connected; command input is forwarded to Bash in the Docker lab, not run by the host backend.

Start with **Challenge 01: First Contact**. Read the objective before asking for hints. Use the hint button to reveal three levels progressively. Then use **Check objective**; completion is awarded by the backend validator, not by clicking a button or claiming the task is done.

## Developer workflow

For frontend-only iteration, from the project root:

```bash
cd frontend
npm install
npm run dev
```

The Vite server runs on `127.0.0.1:5173` and proxies API/WebSocket paths to the backend. In another terminal run the backend with a prepared `.venv`:

```bash
cd redpanda-labs
PYTHONPATH="$PWD/backend" .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Use Vite's development mode for UI work only. The normal run mode serves the built frontend and API from one origin.

## Tests and diagnostics

```bash
bash scripts/diagnostics.sh
bash scripts/test.sh
```

The recorded backend suite ran with 17 passed and 1 Docker integration test skipped. Python compilation and shell-script syntax checks passed. Frontend checks remain blocked because npm dependencies and a committed lockfile could not be obtained in the packaging environment. A successful backend unit-test run does not mean the container security boundary or full end-to-end workflow has passed. See [`docs/TESTING.md`](docs/TESTING.md) and [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

## Data locations

- Source: the folder you extracted.
- SQLite database and managed exports: `~/.local/share/redpanda-labs/`.
- AI provider credentials/settings: `~/.config/redpanda-labs/ai.json`.
- Cache: `~/.cache/redpanda-labs/`.
- Docker workspaces: application-labelled named Docker volumes; not in the source tree.
- Development-only `.test-data`, `.test-config`, and `.test-cache` directories may be created if the test script is run from the project root; they are ignored by Git.

File permissions protect the AI settings from other local users but do **not** encrypt the key. Do not put secrets into challenge files or notes.

## GitHub

The project is initialized as source only; no GitHub login or remote is configured for you. From the project root:

```bash
git status --short
git init
git add .
git commit -m "Build RedPanda Labs starter platform"
git remote add origin YOUR_EXISTING_REPOSITORY_URL
git push -u origin main
```

If the folder is already connected to a repository, do not run `git remote add origin` again; inspect `git remote -v` first. Never commit `.venv`, `node_modules`, local SQLite databases, AI credentials, workspace archives, or challenge command history.

## Important safety note

Use only the built-in local training challenges and systems you own or have explicit permission to test. Do not use these lessons as authorization to assess third-party systems. Deliberately vulnerable web exercises must remain confined to their disposable, private lab environment. Docker reduces risk but does not eliminate kernel/runtime vulnerabilities or all host compromise risk. Do not use the platform to run unreviewed custom scripts until isolated script execution is implemented and independently tested.

## Licence

Provisional MIT license for project code. Review the copyright holder and license choice before public release. Third-party dependencies remain under their own licenses.
