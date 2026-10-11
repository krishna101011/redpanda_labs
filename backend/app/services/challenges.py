from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.config import DATA_DIR, PROJECT_ROOT
from app.models import ChallengeOverride


class Hint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: int = Field(ge=1, le=3)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=6000)


class ChallengeManifest(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = Field(ge=1, le=1)
    id: str = Field(pattern=r"^(challenge-[0-9]{2}|custom-[a-z0-9]+(?:-[a-z0-9]+)*)$")
    version: str = Field(min_length=1, max_length=24)
    title: str = Field(min_length=1, max_length=120)
    track: str = Field(min_length=1, max_length=80)
    difficulty: str = Field(pattern=r"^(Beginner|Intermediate|Advanced)$")
    summary: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=6000)
    learning_objectives: list[str] = Field(min_length=1, max_length=20)
    prerequisites: list[str] = Field(max_length=15)
    tags: list[str] = Field(max_length=30)
    environment_profile: str = Field(max_length=80)
    workspace_seed: dict[str, str] = Field(default_factory=dict)
    offline_hints: list[Hint] = Field(min_length=3, max_length=3)
    validation: dict[str, Any]
    reset_policy: str = Field(max_length=80)
    completion_explanation: str = Field(max_length=6000)
    optional_extensions: list[str] = Field(default_factory=list, max_length=20)
    network_requirements: dict[str, Any]
    estimated_minutes: int = Field(ge=1, le=600)

    @field_validator("prerequisites")
    @classmethod
    def unique_prerequisites(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Prerequisites must be unique")
        return value


def safe_relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 240 or "\x00" in raw or "\\" in raw:
        raise ValueError("File path is invalid")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("File path must stay inside the challenge workspace")
    if path.parts and path.parts[0] in {"proc", "sys", "dev", ".git"}:
        raise ValueError("This path is not allowed in a challenge workspace")
    return str(path)


def validate_manifest(raw: dict[str, Any], *, trusted_builtin: bool = False) -> dict[str, Any]:
    parsed = ChallengeManifest.model_validate(raw)
    data = parsed.model_dump(mode="json")
    if len(data["workspace_seed"]) > 250:
        raise ValueError("A challenge can seed at most 250 files")
    total_bytes = 0
    clean_seed: dict[str, str] = {}
    for path, content in data["workspace_seed"].items():
        clean_path = safe_relative_path(path)
        if not isinstance(content, str):
            raise ValueError("Challenge seed files must be UTF-8 text")
        total_bytes += len(content.encode("utf-8"))
        if total_bytes > 2 * 1024 * 1024:
            raise ValueError("Challenge seed content exceeds 2 MiB")
        clean_seed[clean_path] = content
    data["workspace_seed"] = clean_seed
    validator = data["validation"].get("type")
    allowed = {"text_lines", "exact_file", "json_subset", "file_mode"}
    if trusted_builtin:
        allowed.add("process_stopped")
    if validator not in allowed:
        raise ValueError(f"Unsupported validator type: {validator!r}")
    for key in ("path", "pid_file"):
        if key in data["validation"]:
            data["validation"][key] = safe_relative_path(data["validation"][key])
    if data["id"].startswith("custom-") and "trusted_startup" in data:
        data.pop("trusted_startup", None)
    return data


def builtin_path() -> Path:
    return PROJECT_ROOT / "challenge_packs" / "builtin"


def load_builtins() -> list[dict[str, Any]]:
    folder = builtin_path()
    manifests: list[dict[str, Any]] = []
    for path in sorted(folder.glob("challenge-*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(validate_manifest(raw, trusted_builtin=True))
    ids = {manifest["id"] for manifest in manifests}
    if len(ids) != 15:
        raise RuntimeError(f"Expected exactly 15 built-in challenges; found {len(ids)}")
    for manifest in manifests:
        missing = set(manifest["prerequisites"]) - ids
        if missing:
            raise RuntimeError(f"{manifest['id']} references missing prerequisite(s): {sorted(missing)}")
    _check_prerequisite_cycles(manifests)
    return manifests


def _check_prerequisite_cycles(manifests: list[dict[str, Any]]) -> None:
    graph = {m["id"]: m["prerequisites"] for m in manifests}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise RuntimeError(f"Circular challenge prerequisite detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for item in graph.get(node, []):
            visit(item)
        visiting.remove(node)
        visited.add(node)

    for item in graph:
        visit(item)


def registry(session: Session | None = None, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    builtins = {m["id"]: m for m in load_builtins()}
    if session is None:
        return list(builtins.values())
    overrides = session.query(ChallengeOverride).all()
    for row in overrides:
        if row.disabled and not include_disabled:
            builtins.pop(row.challenge_id, None)
            continue
        custom = json.loads(row.manifest_json)
        if row.is_custom:
            builtins[row.challenge_id] = validate_manifest(custom, trusted_builtin=False)
        else:
            base = builtins.get(row.challenge_id)
            if base:
                # A user override may customise supported learning metadata, but never runtime privilege policy.
                for key in ("title", "track", "difficulty", "summary", "description", "learning_objectives", "prerequisites", "tags", "offline_hints", "validation", "completion_explanation", "estimated_minutes"):
                    if key in custom:
                        base[key] = custom[key]
    return sorted(builtins.values(), key=lambda m: m["id"])


def get_manifest(challenge_id: str, session: Session | None = None) -> dict[str, Any] | None:
    return next((item for item in registry(session) if item["id"] == challenge_id), None)


def override_file(challenge_id: str) -> Path:
    if not re.fullmatch(r"(?:challenge-[0-9]{2}|custom-[a-z0-9]+(?:-[a-z0-9]+)*)", challenge_id):
        raise ValueError("Invalid challenge identifier")
    return DATA_DIR / "challenge_overrides" / f"{challenge_id}.json"
