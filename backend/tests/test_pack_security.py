from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.main import _read_pack
from app.services.challenges import load_builtins


def _zip_with(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_valid_manifest_pack_is_parsed_without_executing_payloads() -> None:
    manifest = next(item for item in load_builtins() if item["id"] == "challenge-01")
    manifest = dict(manifest)
    manifest["id"] = "custom-pack-security-demo"
    body = _zip_with({"challenge.json": json.dumps(manifest).encode(), "README.md": b"Static text only."})
    result = _read_pack(body)
    assert result["id"] == "custom-pack-security-demo"
    assert "trusted_startup" not in result


def test_archive_path_traversal_and_script_payloads_are_rejected() -> None:
    manifest = next(item for item in load_builtins() if item["id"] == "challenge-01")
    manifest = dict(manifest)
    manifest["id"] = "custom-pack-safe"
    content = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="Unsafe path"):
        _read_pack(_zip_with({"challenge.json": content, "../escape.txt": b"no"}))
    with pytest.raises(ValueError, match="Unsupported file"):
        _read_pack(_zip_with({"challenge.json": content, "setup.sh": b"touch /tmp/should-not-run"}))


def test_bad_zip_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid ZIP"):
        _read_pack(b"not a zip file")
