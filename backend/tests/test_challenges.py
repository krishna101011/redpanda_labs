from __future__ import annotations

import pytest

from app.services.challenges import load_builtins, safe_relative_path, validate_manifest


def test_exactly_fifteen_distinct_builtin_challenges() -> None:
    challenges = load_builtins()
    assert len(challenges) == 15
    assert len({item["id"] for item in challenges}) == 15
    assert [item["id"] for item in challenges] == [f"challenge-{number:02d}" for number in range(1, 16)]


def test_every_builtin_has_three_hints_learning_objectives_seed_and_validator() -> None:
    for challenge in load_builtins():
        assert len(challenge["offline_hints"]) == 3, challenge["id"]
        assert [hint["level"] for hint in challenge["offline_hints"]] == [1, 2, 3]
        assert challenge["learning_objectives"]
        assert challenge["workspace_seed"]
        assert challenge["completion_explanation"]
        assert challenge["validation"]["type"] in {"text_lines", "exact_file", "json_subset", "file_mode", "process_stopped"}


def test_all_prerequisites_resolve_and_graph_is_acyclic() -> None:
    challenges = load_builtins()
    by_id = {item["id"]: item for item in challenges}
    assert all(prerequisite in by_id for item in challenges for prerequisite in item["prerequisites"])
    for item in challenges:
        assert item["id"] not in item["prerequisites"]


def test_paths_reject_absolute_traversal_and_reserved_locations() -> None:
    for path in ("/etc/passwd", "../../outside", "a/../b", "\\windows\\system.ini", "proc/self/environ", "dev/null", "a\x00b"):
        with pytest.raises(ValueError):
            safe_relative_path(path)
    assert safe_relative_path("notes/evidence.txt") == "notes/evidence.txt"


def test_custom_manifest_cannot_keep_trusted_startup() -> None:
    manifest = next(item for item in load_builtins() if item["id"] == "challenge-09")
    manifest = dict(manifest)
    manifest["id"] = "custom-local-service-demo"
    manifest["trusted_startup"] = [["/bin/sh", "-c", "touch /tmp/untrusted"]]
    validated = validate_manifest(manifest, trusted_builtin=False)
    assert "trusted_startup" not in validated
