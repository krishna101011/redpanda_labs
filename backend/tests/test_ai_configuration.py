from __future__ import annotations

import json
import stat

import pytest

from app.services.ai import AIConfigurationError, config_path, delete_settings, read_settings, save_settings, validate_base_url


def test_credentials_are_saved_owner_only_but_never_returned_in_settings() -> None:
    result = save_settings({"provider": "Local mock", "base_url": "http://127.0.0.1:1234/v1", "model": "example-model", "api_key": "test-secret-value", "timeout_seconds": 15})
    path = config_path()
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert result["api_key_saved"] is True
    assert "api_key" not in result
    assert "test-secret-value" not in json.dumps(result)
    assert json.loads(path.read_text())["api_key"] == "test-secret-value"
    delete_settings()
    assert not path.exists()
    assert read_settings()["api_key_saved"] is False


def test_remote_http_and_embedded_credentials_are_rejected() -> None:
    with pytest.raises(AIConfigurationError):
        validate_base_url("http://api.example.com/v1")
    with pytest.raises(AIConfigurationError):
        validate_base_url("https://user:pass@api.example.com/v1")
    assert validate_base_url("https://api.example.com/v1") == "https://api.example.com/v1"
