from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Isolate all application state from the host user's real RedPanda Labs data during tests.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="redpanda-labs-tests-"))
os.environ["REDPANDA_DATA_DIR"] = str(_TEST_ROOT / "data")
os.environ["REDPANDA_CONFIG_DIR"] = str(_TEST_ROOT / "config")
os.environ["REDPANDA_CACHE_DIR"] = str(_TEST_ROOT / "cache")
os.environ["REDPANDA_DATABASE_URL"] = f"sqlite:///{_TEST_ROOT / 'data' / 'tests.sqlite3'}"

for _path in (_TEST_ROOT / "data", _TEST_ROOT / "config", _TEST_ROOT / "cache"):
    _path.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        _path.chmod(0o700)
    except OSError:
        pass
