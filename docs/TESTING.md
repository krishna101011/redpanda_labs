# Testing and release criteria

Run from the project root after dependencies are prepared:

```bash
bash scripts/diagnostics.sh
bash scripts/test.sh
```

The full test script runs backend pytest tests, TypeScript type checking, ESLint, and frontend Vitest tests. Backend tests cover the manifest registry and prerequisite graph, API basics, AI-setting secrecy/permissions, archive/path validation, and validator behavior where it can be tested without Docker. Docker integration tests are opt-in and should skip with a clear reason if the daemon is absent.

## Results from the packaging environment (11 October 2026)

- `PYTHONPATH=backend python -m pytest -q backend/tests`: **17 passed, 1 skipped**. The skipped test requires a real Docker daemon and the `redpanda-labs:0.1.0` image.
- `python -m compileall -q backend/app backend/alembic backend/tests`: **passed**.
- `bash -n` on all five scripts under `scripts/`: **passed**.
- Docker integration, image build, genuine terminal and networking isolation tests: **blocked/not run**, since the `docker` executable is not installed in the build environment.
- Frontend typecheck, ESLint, Vitest and production build: **not run**, because frontend packages could not be downloaded. npm lockfile generation timed out while trying to reach the package registry. The project does not yet contain `frontend/package-lock.json`.

The package is therefore **not release-ready**, despite passing its runnable backend unit/API suite and static shell/Python checks.

## Required integration test track

On a dedicated Linux Mint test machine with Docker and npm registry access:

1. Run a fresh setup; verify the frontend lockfile/build and that migrations apply twice without data loss.
2. Open the dashboard and verify Docker/image readiness.
3. Start Challenge 01, execute `pwd`, `whoami`, and `ls` in the real Bash terminal; verify it is inside the lab container, not the host context.
4. Create the report, check objective, verify the completion record and unlock behavior.
5. Reload browser and reconnect to the session; check terminal resize, Ctrl+C, output streaming, restart-shell and workspace-reset distinction.
6. Complete one mission for each validator type and run smoke tests for all 15 challenges.
7. Verify workspace persistence across app restart and expected recovery after a computer reboot.
8. Test archive export/restore, progress/notes export/restore merge and replace, single/all progress resets, deletion confirmation, and that unrelated Docker resources remain untouched.
9. Verify that a default isolated challenge cannot reach the public Internet; verify internal service target access only from the intended internal lab network; confirm challenge service ports are not published on the host.
10. Verify cross-challenge reachability is denied and gateway destination/session validation after a browser gateway exists.
11. Exercise valid, invalid, oversized, traversal, symlink and malformed archives; confirm none executes scripts during import.
12. Test the AI adapter with a local mock HTTP service for success, invalid credential, timeout, 429, redirect and malformed response; confirm no credential is returned or logged.
13. Run the full end-to-end journey after repeat startup and confirm data remains consistent.

## Integrity rules

- A unit test using mocks does not prove actual container/network behavior.
- A manifest test does not prove a challenge can be solved end-to-end in its shell.
- An HTTP health response does not prove the UI terminal can reconnect.
- A Docker integration test not run due to missing Docker must be shown as **blocked/not run**, not passed.
- The diagnostics API intentionally reports `release_ready: false` until independent release checks are completed.
