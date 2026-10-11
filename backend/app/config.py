from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "RedPanda Labs"
APP_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "redpanda-labs"
DATA_DIR = Path(os.environ.get("REDPANDA_DATA_DIR", DEFAULT_DATA_DIR)).expanduser().resolve()
CONFIG_DIR = Path(os.environ.get("REDPANDA_CONFIG_DIR", Path.home() / ".config" / "redpanda-labs")).expanduser().resolve()
CACHE_DIR = Path(os.environ.get("REDPANDA_CACHE_DIR", Path.home() / ".cache" / "redpanda-labs")).expanduser().resolve()
DATABASE_URL = os.environ.get("REDPANDA_DATABASE_URL", f"sqlite:///{DATA_DIR / 'redpanda.sqlite3'}")
LAB_IMAGE = os.environ.get("REDPANDA_LAB_IMAGE", "redpanda-labs:0.1.0")
HOST = os.environ.get("REDPANDA_HOST", "127.0.0.1")
PORT = int(os.environ.get("REDPANDA_PORT", "8000"))
LOG_LEVEL = os.environ.get("REDPANDA_LOG_LEVEL", "INFO").upper()
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_FILES = 250
MAX_FILE_BYTES = 1024 * 1024


def ensure_data_directories() -> None:
    for path in (DATA_DIR, CONFIG_DIR, CACHE_DIR, DATA_DIR / "challenge_overrides", DATA_DIR / "backups"):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.chmod(0o700)
        except OSError:
            pass
