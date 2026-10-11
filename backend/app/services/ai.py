from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import httpx

from app.config import CONFIG_DIR, ensure_data_directories


class AIConfigurationError(ValueError):
    pass


def config_path() -> Path:
    return CONFIG_DIR / "ai.json"


def validate_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AIConfigurationError("Enter a full HTTP(S) base URL, such as https://api.example.com/v1 or http://127.0.0.1:1234/v1.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIConfigurationError("The AI base URL must not contain credentials, a query string, or a fragment.")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and parsed.hostname not in local_hosts:
        raise AIConfigurationError("Use HTTPS for remote AI providers. Plain HTTP is allowed only for a local model service.")
    return value


def read_settings() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {"configured": False, "provider": "OpenAI-compatible", "base_url": "", "model": "", "api_key_saved": False, "timeout_seconds": 20}
    try:
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            return {"configured": True, "provider": "OpenAI-compatible", "base_url": "", "model": "", "api_key_saved": True, "timeout_seconds": 20, "warning": "AI credentials file permissions are broader than owner-only. Use `chmod 600 ~/.config/redpanda-labs/ai.json`."}
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"configured": False, "provider": "OpenAI-compatible", "base_url": "", "model": "", "api_key_saved": False, "timeout_seconds": 20, "warning": "AI configuration could not be read. Re-save settings after checking the file."}
    return {"configured": bool(saved.get("base_url") and saved.get("model")), "provider": saved.get("provider", "OpenAI-compatible"),
            "base_url": saved.get("base_url", ""), "model": saved.get("model", ""), "api_key_saved": bool(saved.get("api_key")),
            "timeout_seconds": int(saved.get("timeout_seconds", 20))}


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_data_directories()
    base_url = validate_base_url(str(payload.get("base_url", "")))
    model = str(payload.get("model", "")).strip()
    provider = str(payload.get("provider", "OpenAI-compatible")).strip()[:100]
    timeout_seconds = int(payload.get("timeout_seconds", 20))
    if not model or len(model) > 200:
        raise AIConfigurationError("Model name is required and must be at most 200 characters.")
    if not 3 <= timeout_seconds <= 120:
        raise AIConfigurationError("Request timeout must be between 3 and 120 seconds.")
    path = config_path()
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    key = str(payload.get("api_key", "")).strip() or existing.get("api_key", "")
    if len(key) > 2000:
        raise AIConfigurationError("API key appears too long.")
    saved = {"provider": provider or "OpenAI-compatible", "base_url": base_url, "model": model,
             "api_key": key, "timeout_seconds": timeout_seconds}
    path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise AIConfigurationError("Could not secure AI configuration file permissions. Check the configuration directory.") from exc
    return read_settings()


def delete_settings() -> None:
    path = config_path()
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise AIConfigurationError("Could not remove the saved AI configuration file.") from exc


async def ask_ai(messages: list[dict[str, str]], *, max_tokens: int = 800) -> str:
    path = config_path()
    if not path.exists():
        raise AIConfigurationError("AI is not configured. Offline hints are available without an API key.")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise AIConfigurationError("AI credential file permissions are too broad. Run chmod 600 on ~/.config/redpanda-labs/ai.json.")
    saved = json.loads(path.read_text(encoding="utf-8"))
    base_url = validate_base_url(saved.get("base_url", ""))
    model = saved.get("model", "")
    key = saved.get("api_key", "")
    timeout = int(saved.get("timeout_seconds", 20))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        if response.status_code in (301, 302, 303, 307, 308):
            raise AIConfigurationError("The AI endpoint redirected the request. Redirects are blocked to protect credentials.")
        if response.status_code in (401, 403):
            raise AIConfigurationError("The AI provider rejected the credentials. Check the key and endpoint in Settings.")
        if response.status_code == 429:
            raise AIConfigurationError("The AI provider is rate-limiting requests. Use offline hints or try again later.")
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise AIConfigurationError("The AI provider returned an empty or unexpected response.")
        return content[:12000]
    except AIConfigurationError:
        raise
    except httpx.TimeoutException as exc:
        raise AIConfigurationError("The AI provider timed out. Offline hints are still available.") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIConfigurationError(f"The AI provider could not be reached or returned an unsupported response ({type(exc).__name__}).") from exc
