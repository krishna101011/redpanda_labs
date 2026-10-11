from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.challenges import load_builtins
from app.services.labs import LabManager


class FakeContainer:
    """Stateful validator test double only. It does not prove Docker behavior."""

    def __init__(self, challenge: dict):
        self.challenge = challenge
        self.rule = challenge["validation"]
        kind = self.rule["type"]
        self.files: dict[str, str] = dict(challenge.get("workspace_seed", {}))
        if kind == "text_lines":
            self.files[self.rule["path"]] = "\n".join(self.rule["required_lines"]) + "\n"
        elif kind == "exact_file":
            self.files[self.rule["path"]] = self.rule["content"]
        elif kind == "json_subset":
            self.files[self.rule["path"]] = json.dumps(self.rule["expected"])
        elif kind == "process_stopped":
            self.files[self.rule["pid_file"]] = "424242\n"

    def exec_run(self, argv, **kwargs):
        if argv[0] == "cat":
            path = argv[-1].removeprefix("/workspace/")
            if path not in self.files:
                return SimpleNamespace(exit_code=1, output=(b"", b""))
            return SimpleNamespace(exit_code=0, output=(self.files[path].encode(), b""))
        if argv[0] == "stat":
            path = argv[-1].removeprefix("/workspace/")
            if "-c" in argv and "%a" in argv:
                value = self.rule.get("mode", "600")
            else:
                value = self.rule.get("owner", "redpanda")
            return SimpleNamespace(exit_code=0 if path in self.files else 1, output=(f"{value}\n".encode(), b""))
        if len(argv) > 2 and "test -d /proc/" in argv[2]:
            return SimpleNamespace(exit_code=1, output=(b"", b""))
        return SimpleNamespace(exit_code=0, output=(b"", b""))


def test_each_of_fifteen_challenge_validators_checks_expected_state(monkeypatch) -> None:
    manager = LabManager()
    for challenge in load_builtins():
        container = FakeContainer(challenge)
        monkeypatch.setattr(manager, "container_for", lambda challenge_id, c=container: c)
        valid, feedback, evidence = manager.validate(challenge, db=None)
        assert valid, (challenge["id"], feedback, evidence)
        assert feedback
        assert isinstance(evidence, dict)


def test_validator_rejects_missing_evidence(monkeypatch) -> None:
    challenge = next(item for item in load_builtins() if item["id"] == "challenge-01")
    container = FakeContainer(challenge)
    container.files.pop(challenge["validation"]["path"])
    manager = LabManager()
    monkeypatch.setattr(manager, "container_for", lambda challenge_id: container)
    valid, feedback, evidence = manager.validate(challenge, db=None)
    assert valid is False
    assert "missing" in feedback[0].lower()
    assert evidence["file_exists"] is False
