# Security model and limitations

## Intended use

RedPanda Labs is a local learning application for the owner's Linux computer. Keep it bound to `127.0.0.1`. The first release has no accounts, public server, telemetry, remote analytics, or social features. Use it only for labs and authorized learning.

## Main threat assumptions

Treat a challenge shell as untrusted: commands may be malformed, consume resources, modify that challenge's workspace, and attempt to access anything visible from its container. Treat imported manifest data, archive files, notebook text, and AI output as untrusted. Treat the Docker daemon and host kernel as privileged infrastructure.

## Defenses present in source

- API host validation, loopback-oriented server configuration, strict WebSocket origin checks, limited CORS origins, Pydantic request validation, and bounded request/body/archive fields.
- JSON manifest validation, known validator types, prerequisite validation, safe relative-path checks, and no user-defined Docker daemon flags or host mounts.
- Docker-owned named workspace volumes, application/challenge labels, ownership checks before modifying existing resources, non-root lab user, dropped capabilities, `no-new-privileges`, read-only container root, temporary filesystem limits, and memory/CPU/PID bounds.
- Default network isolation (`network_mode=none`), and internal-only networks for local-service challenges.
- AI keys written outside the source folder to an owner-only file; redirects are blocked, remote non-TLS endpoints are rejected, and credentials are not returned in API responses.
- Safe workspace archive checks for entry count, path, regular-file/directory types, per-file/total limits, and symlinks/device entries.
- No use of challenge input with `os.system`, `shell=True`, or a host shell. Application-managed Docker operations use API calls and validated fixed configuration.

## Security limitations

1. **Docker is not a perfect isolation boundary.** Container/runtime/kernel defects can put a host at risk. Rootless Docker is preferred where supported; the app will not silently change host privileges or daemon configuration.
2. **The current build was not able to run Docker tests.** Resource flags, network isolation, PTY attach behavior, reset/restore behavior and resource ownership checks require validation on supported Linux Mint systems.
3. **The session-restricted web challenge gateway is not implemented.** Do not expose training services through published ports or build an ad hoc proxy around these endpoints.
4. **Custom scripts are not implemented as executable features.** Custom challenge packs are declarative only. Do not assume user-supplied code can be safely executed.
5. Some networking lessons require local internal service behavior. The exact isolation must be proven by the Docker integration tests, not inferred from manifest names.
6. The app is designed for one local learner, not hostile multi-user operation. A same-user process on the same machine may have substantial access to the local user's files.
7. AI provider settings use file permissions, not encryption. Sending a question or selected terminal output shares that content with the configured endpoint. Never send secrets or unrelated private files.
8. The current application does not claim production hardening, formal threat-model validation, or independent penetration-test status.

## Safe operating rules

- Do not expose port 8000 beyond loopback.
- Do not mount the Docker socket or host home folder into a challenge.
- Do not remove or modify Docker resources unless they have the application labels and matching challenge ID.
- Do not add host networking, host PID namespaces, privileged mode, host mounts, devices, or unrestricted external networking to a challenge.
- Do not import and execute arbitrary scripts.
- Use only the built-in local challenges and authorized training targets.
- Inspect `bash scripts/diagnostics.sh` and run `bash scripts/test.sh` after upgrades.
