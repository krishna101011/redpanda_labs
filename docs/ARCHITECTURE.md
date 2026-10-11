# Architecture

## Runtime map

```text
Browser (127.0.0.1:8000)
   ├── React + TypeScript + Vite-built static assets
   ├── HTTP JSON requests (/api/*)
   └── WebSocket (/api/terminal/{challenge_id})
             │
             ▼
FastAPI native process (current Linux user, loopback only)
   ├── API routes and local browser security checks
   ├── SQLAlchemy models + Alembic migrations
   ├── challenge registry and manifest validation
   ├── state-based validation service
   ├── Docker manager (managed labels + named volumes)
   ├── PTY/session manager (docker exec; learner text is PTY input)
   ├── offline/optional hosted AI adapter
   └── export/import and notebook/progress services
             │
             ▼
Docker Engine (separate trust boundary)
   ├── redpanda-labs:0.1.0, non-root challenge user
   ├── one named workspace volume per challenge
   ├── no network for most challenges
   └── challenge-specific internal networks for local service tasks
```

## Frontend

`frontend/src/App.tsx` implements the app shell and primary views. `frontend/src/api.ts` centralizes API calls and download behavior. `TerminalPanel.tsx` uses xterm.js and its fit addon; terminal input/output is carried on the challenge WebSocket. CSS is in `styles.css` and uses a responsive charcoal/red visual system, keyboard focus states, and reduced-motion behavior.

During UI development, Vite serves on `127.0.0.1:5173` and proxies API/WebSocket requests to `127.0.0.1:8000`. The normal app is a single-origin build served by FastAPI from `frontend/dist`.

## Backend

- `app/main.py`: transport/API layer, validation, permissions, progress recording and frontend serving. Route handlers call service modules.
- `app/config.py`: paths and runtime defaults.
- `app/database.py`: SQLAlchemy engine/session creation and Alembic upgrade.
- `app/models.py`: progress, completion history, achievements, notes, preferences, workspace registry and challenge overrides.
- `app/services/challenges.py`: JSON manifest validation, trusted built-in loading, prerequisite-cycle checks, override/custom challenge registry and path rules.
- `app/services/labs.py`: Docker API integration, managed resource labels, image checks, challenge workspace seed/reset/export/restore and state validators.
- `app/services/terminal.py`: PTY-backed session objects, input/output and resize operations.
- `app/services/ai.py`: OpenAI-compatible chat-completion adapter, private local settings file, URL validation, no redirects and credential-safe error handling.
- `alembic/`: versioned SQLite schema.

The database is local. The shell history is stored in each challenge workspace, not copied into the SQLite database.

## Challenge manifests

Each built-in challenge is a versioned JSON file in `challenge_packs/builtin/`. The schema describes objectives, prerequisites, tags, starter files, hints, validator configuration, reset behavior, completion explanation and networking requirements. `load_builtins()` validates all files and ensures there are exactly 15 with no missing prerequisite IDs or cycles. Runtime progress and user edits are stored separately from packaged definitions.

## Terminal and workspace lifecycle

A challenge maps deterministically to an application-prefixed container, named volume and (where required) private network. Resources are labelled with the product and challenge ID. Management code checks labels before modifying existing resources. Workspace data does not use a host bind mount. A shell attaches via a PTY and `docker exec` to a tmux-managed Bash session inside the container. tmux keeps the logical shell alive across browser/backend reconnects where the container remains alive. UI input is never used as an argument to a host shell.

The container is non-root, drops Linux capabilities, uses `no-new-privileges`, read-only root filesystem, writable workspace volume, a bounded `/tmp`, and CPU/memory/process limits. Networking is disabled for most missions. Some service lessons need an internal Docker network. The current code has not had real Docker security/integration tests in this build environment, and Docker itself is not a perfect security boundary.

## Known architecture gaps

The session-restricted browser gateway required for safely previewing vulnerable web targets is not yet implemented. Therefore web service investigation currently takes place through the isolated shell/network model, rather than through a hardened in-app browser proxy. User-defined custom setup/validator scripts are not enabled; pack import explicitly rejects script payloads. These gaps are listed as outstanding release blockers in `PROJECT_STATUS.md`.
