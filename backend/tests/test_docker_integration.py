from __future__ import annotations

import copy
import importlib.util
import os
import shutil
import time

import pytest

from app.database import SessionLocal, run_migrations
from app.services.challenges import load_builtins
from app.services.labs import LabManager

_DOCKER_TESTS_ENABLED = (
    os.environ.get("REDPANDA_DOCKER_TESTS") == "1"
    and shutil.which("docker") is not None
    and importlib.util.find_spec("docker") is not None
)
pytestmark = pytest.mark.skipif(
    not _DOCKER_TESTS_ENABLED,
    reason="Docker integration tests require REDPANDA_DOCKER_TESTS=1, Docker CLI/SDK, a reachable daemon, and redpanda-labs:0.1.0. Not run in the build environment.",
)


def _with_test_id(source: dict, test_id: str) -> dict:
    result = copy.deepcopy(source)
    result["id"] = test_id
    return result


def _curl(container, url: str):
    # argv list; the test URL is fixed by this test and never comes from the challenge UI.
    return container.exec_run(["curl", "--fail", "--silent", "--show-error", "--connect-timeout", "2", "--max-time", "4", url], user="redpanda")


def test_private_service_is_reachable_only_inside_its_isolated_challenge() -> None:
    run_migrations()
    manager = LabManager()
    db = SessionLocal()
    target_id = "integration-test-target"
    client_id = "integration-test-client"
    try:
        builtins = {item["id"]: item for item in load_builtins()}
        target = _with_test_id(builtins["challenge-09"], target_id)
        client = _with_test_id(builtins["challenge-01"], client_id)
        manager.ensure_workspace(target, db)
        target_container = manager.container_for(target_id)

        # The expected internal target must really respond from its own challenge.
        response = None
        for _ in range(20):
            response = _curl(target_container, "http://127.0.0.1:8080/health")
            if response.exit_code == 0:
                break
            time.sleep(0.25)
        assert response is not None and response.exit_code == 0, "Local training API was not reachable inside its lab."
        assert b'"service":"training-api"' in response.output

        # Challenge services are private and no host-facing port is published.
        target_container.reload()
        assert not (target_container.attrs.get("HostConfig", {}).get("PortBindings") or {})
        assert target_container.attrs.get("HostConfig", {}).get("NetworkMode") != "host"

        manager.ensure_workspace(client, db)
        client_container = manager.container_for(client_id)
        client_container.reload()
        assert client_container.attrs.get("HostConfig", {}).get("NetworkMode") == "none"

        # No outbound Internet route in a normal challenge and no cross-challenge route to the service.
        external = _curl(client_container, "https://example.com/")
        assert external.exit_code != 0, "A no-network challenge reached the public Internet."
        cross_challenge = _curl(client_container, "http://redpanda-labs-integration-test-target:8080/health")
        assert cross_challenge.exit_code != 0, "A normal challenge reached another challenge's private service."
    finally:
        for challenge_id in (client_id, target_id):
            try:
                manager.cleanup_registered_workspace(challenge_id, db)
            except Exception as exc:  # keep attempting cleanup for both uniquely named test resources
                pytest.fail(f"Could not clean test resource {challenge_id}: {type(exc).__name__}")
        db.close()
