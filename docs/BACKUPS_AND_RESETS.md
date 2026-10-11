# Backups, restore and reset behavior

These operations represent separate data layers. Read the confirmation text before accepting destructive changes.

## Progress and notes export

Exported JSON includes supported progress/completion history, achievements, notebook entries and preferences. AI credentials and Docker workspace files are excluded. An import can be previewed before merge/replace; review counts and warnings first. The export format is versioned, and malformed versions/data are rejected.

## Workspace archive

A workspace archive contains only the files Docker reports for the selected application-managed `/workspace`. It is not the same as progress export and does not include host paths outside that volume. Restore validates archive size, member count, paths, file type and per-file/total content. Use it only with a selected lab workspace.

## Challenge pack

A challenge pack carries a manifest and permitted static documentation, not personal learning records, API credentials, or workspace files. Executable setup/validator script payloads are currently unsupported and must be rejected.

## Reset a single workspace

Reset the selected challenge's files to its starter state, without touching other challenge volumes. Personal notes and historical completion records are intended to remain intact. Shell restart is a different operation: it restarts the shell process but keeps the workspace files.

## Clear one challenge's progress

This clears the current progress state for that challenge and updates unlock calculation. It is separate from resetting workspace files; notes, current workspace data and historical completion/achievement records are preserved unless another explicit operation says otherwise.

## Reset all learning progress

This clears active progress and current achievement state from the progress view. It preserves notes, separately saved explanations and workspaces by default. Export first if you may need the old progress.

## Delete application data

This operation requires an explicit confirmation phrase and removes the application's progress, notes, preferences, overrides, history and application-managed lab resources. It must never clean unrelated containers or volumes and must not delete arbitrary host files. API credentials stored in `~/.config/redpanda-labs/ai.json` are a separate setting and can be deleted from the AI settings control.

## Verify before trusting

Backup paths and reset logic are implemented in source, but full real-Docker workspace archive and reset behavior has not been exercised in this build environment. Treat those flows as awaiting integration verification until `docs/TESTING.md`'s container tests pass on a supported Linux host.
