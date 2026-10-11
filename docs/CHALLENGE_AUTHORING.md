# Challenge authoring guide

Built-in challenges live in `challenge_packs/builtin/challenge-NN.json`. Each manifest is JSON, currently `schema_version: 1`, and uses stable IDs such as `challenge-01`.

## Supported fields

A manifest contains an ID/version/title, track and difficulty, concise summary/description, learning objectives, prerequisites, tags, environment profile, starter workspace files, three progressive offline hints, validator configuration, reset policy, completion explanation, optional extensions, networking requirements and estimated minutes. Built-in-only operational metadata can specify an approved startup service or special starter-file modes. Do not copy those privileged settings into a custom challenge.

## Starter files

`workspace_seed` maps safe relative workspace paths to UTF-8 text. Paths must stay under `/workspace`; absolute paths, `..`, backslashes, NUL characters and restricted top-level paths are rejected. Keep starter material deterministic and synthetic. The lab manager seeds files into an application-owned Docker named volume, not a host bind mount.

## Validator types

- `text_lines`: a report must contain each configured required line.
- `exact_file`: a generated file must match the configured normalized content exactly.
- `json_subset`: a JSON object must match configured key/value pairs.
- `file_mode`: a workspace file must have the expected numeric mode and owner.
- `process_stopped`: built-in-only validation verifies that a recorded PID no longer represents a running process in that same lab.

Validators read actual workspace state. They do not trust a frontend answer, a button click, or shell-history text as proof. Keep hidden acceptance details to the necessary degree; feedback should help the learner improve without listing every missing secret check in advance.

## Prerequisites

Prerequisite IDs must exist and the graph must remain acyclic. A challenge should have no prerequisite for its own ID. Optional side missions should not be tied into an unnecessarily linear path.

## Hints and explanations

Include exactly three hints: conceptual nudge, investigation direction, and detailed guidance. The detailed hint can explain reasoning but should be consistent with the intended reveal policy. Completion explanations should cover how validation works, common mistakes, and how the skill maps to real defensive/security work.

## Challenge Builder limitations

The app supports declarative user-defined challenges, metadata edits, known validator types, previews, disable/restore, and challenge-pack export/import. Imported archives are bounded and validated; unsupported executable payloads are rejected. **Custom setup and validator scripts are not implemented**, and must not be presented as runnable. Do not add Dockerfile import, host mounts, Docker flags, privilege controls, or arbitrary network options through the UI.

## Import/export

A challenge pack is separate from progress and workspace archives. Packs do not contain personal notes, progress, credentials, or shell histories. Inspect imported content and validate it before enabling the challenge. The import code should never execute content while parsing the archive.
