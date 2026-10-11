# Project status and build report

**Status: incomplete / awaiting verification. Not release-ready.** The source contains a real React + TypeScript frontend, a FastAPI backend, SQLite/Alembic persistence, fifteen separate challenge manifests, Docker management and terminal code, offline hints, optional AI settings, notebook flows, declarative challenge authoring, backup/reset endpoints, and Linux setup scripts. Several required integrations are either not implemented or could not be verified in this packaging environment. Do not treat this build as a security-reviewed release.

## Implemented in source

- React + TypeScript + Vite workbench with dashboard, catalogue, skill path, challenge workspace, notebook, challenge builder and settings/diagnostics views.
- FastAPI backend with loopback-oriented defaults, SQLite/SQLAlchemy models, Alembic migration, challenge prerequisite graph validation, progress/history, achievements, notes, and saved explanations.
- Fifteen separately authored version-1 built-in JSON challenge manifests, with challenge-specific descriptions, objectives, prerequisites, starter files, three progressive offline hints, and validators.
- An xterm.js frontend and PTY-backed path that attaches to a Docker Bash session using a fixed Docker CLI command. User-entered terminal data is written to the PTY and is not interpolated into a host shell command.
- Docker manager source for labelled containers and named volumes, non-root shell, dropped capabilities, no-new-privileges, memory/CPU/process limits, read-only root filesystem, and restrictive default networking.
- Offline mentor responses and an optional OpenAI-compatible API adapter. Credentials are stored outside the source tree in `~/.config/redpanda-labs/ai.json` with owner-only permissions.
- Notes CRUD, progress/notes export and restore preview, workspace archive logic, declarative challenge-pack export/import, and separated progress/workspace reset operations.
- Linux setup, run, stop, diagnostics and test scripts; setup/troubleshooting guides; architecture, security, authoring, AI and backup documentation; an MIT licence template and Git ignore rules.

## Implemented but not fully verified

- Workspace persistence/reset/restore/ownership code; it has not been exercised against a real Docker daemon in this environment.
- PTY input/output, resizing, reconnect and restart behavior; source exists but was not tested against real containers.
- All fifteen challenge validators have unit-level coverage of the engine/validation rules, but all fifteen missions have **not** been played end-to-end in real containers.
- Local service and internal-network setup for networking missions; actual reachability and isolation were not tested.
- Archive/restore logic and app restart persistence require real workspace integration testing.
- Frontend components are authored, but TypeScript build, lint, Vitest and browser E2E tests were blocked by unavailable npm dependencies.

## Not implemented / release blockers

- A session-restricted browser gateway for authorising browser access to local web challenge targets.
- Safe isolated execution for custom setup/validation scripts. User-defined scripts are intentionally not supported; imported executable payloads must not be run.
- A committed `frontend/package-lock.json`. Direct frontend dependencies have exact versions in `package.json`, but the npm package registry could not be reached from the packaging environment to resolve and generate a transitive lockfile.
- Complete automated end-to-end browser coverage.
- Real Docker image, shell, workspace-volume and network-isolation validation on Linux Mint.
- Formal independent security review.

## Environment and actual test report

Packaging environment: Python 3.13.5, Node.js 22.16.0, npm 10.9.2. The Docker CLI is absent. An npm lockfile-generation attempt timed out; frontend dependencies were not installed. Do not infer frontend build success from the existence of source files.

| Check | Command | Result | Notes |
|---|---|---|---|
| Backend unit/API tests | `PYTHONPATH=backend python -m pytest -q backend/tests` | **PASS: 17 passed, 1 skipped** | The skipped test explicitly requires Docker SDK/CLI, reachable daemon, and built lab image. |
| Python source compilation | `python -m compileall -q backend/app backend/alembic backend/tests` | **PASS** | Syntax/bytecode compilation only, not a substitute for runtime integration. |
| Shell script syntax | `bash -n scripts/setup.sh` and the same for every `scripts/*.sh` | **PASS** | All five shell scripts passed `bash -n`. |
| Built-in manifest loading | Covered by backend challenge/API tests | **PASS as part of backend suite** | Fresh API catalogue returned 15 built-in missions in tests. |
| Docker availability | `docker version` | **BLOCKED** | `docker: command not found`. |
| Frontend dependency installation / lock generation | `npm install --package-lock-only --ignore-scripts --no-audit --no-fund --fetch-timeout=12000 --fetch-retries=0` | **BLOCKED** | Command timed out; registry access could not be established. |
| Frontend typecheck, lint, Vitest, production build | npm scripts | **NOT RUN** | Required frontend dependencies and lockfile are not available in this environment. |
| Real terminal, container, workspace and network isolation tests | Docker integration suite | **NOT RUN / BLOCKED** | Docker is absent; no assertion of real isolation is made. |
| Browser end-to-end workflow | Browser automation | **NOT IMPLEMENTED / NOT RUN** | Manual workflow is documented in `docs/TESTING.md`. |

### Commands used for the successful checks

```bash
PYTHONPATH=backend python -m pytest -q backend/tests
python -m compileall -q backend/app backend/alembic backend/tests
for f in scripts/*.sh; do bash -n "$f"; done
```

The initial bare command `python -m pytest -q backend/tests` from the project root failed collection because `backend/` was not on `PYTHONPATH`; it was rerun with the project test import path set, producing the pass result above. The documented `scripts/test.sh` expects a prepared `.venv` and `frontend/node_modules`, neither of which is included in the source archive.

## Before calling this release-ready

1. On Linux Mint, run setup with registry access; generate and commit `frontend/package-lock.json`; confirm frontend typecheck, lint, unit tests and production build.
2. Install/configure Docker without silently changing system permissions, build `redpanda-labs:0.1.0`, and execute the genuine integration suite.
3. Implement and test the session-restricted web gateway and isolated custom-script executor before exposing those features.
4. Execute the documented full learner journey and network-boundary tests on a dedicated test host.
5. Resolve all failures, review the threat model and only then reconsider release readiness.

Docker is a useful containment layer, not a perfect security boundary. Keep this local-only and use only the built-in training challenges until the missing isolation work has been completed and reviewed.
