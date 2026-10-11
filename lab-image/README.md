# RedPanda Labs training image

This image is built locally by `scripts/setup.sh`. It is a minimal command-line environment for the bundled synthetic exercises. The application starts it with a read-only root filesystem, a named workspace volume, no added Linux capabilities, no-new-privileges, resource limits, and either `network=none` or a dedicated Docker network marked `internal`.

The base tag is `ubuntu:24.04`; it is a maintained tag but is not a content-addressed digest. For a reproducible production release, the base image digest and package versions should be pinned and verified in CI.
