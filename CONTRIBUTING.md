# Development notes

- Keep API routes thin and move reusable logic into service modules.
- Never execute browser-provided terminal text on the host. Terminal input must be sent to the PTY attached to the managed container.
- Add challenges as versioned JSON manifests under `challenge_packs/builtin/`; keep the collection at exactly 15 until the product scope is intentionally revised.
- Validate imported paths, file types, archive size and file counts before extracting any member.
- Keep all user data and AI credentials outside the source tree. Do not add telemetry.
- Run `bash scripts/test.sh` and update `docs/PROJECT_STATUS.md` with true results.
- Do not claim a Docker or network security property based only on a mock test. Run the real test on a disposable, dedicated machine.
- Preserve the separation between progress/notes exports, workspace archives and challenge packs.
- Before a public release, review the provisional MIT license placeholder and dependencies' licenses.
