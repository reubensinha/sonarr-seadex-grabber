"""Tests for core.sync_manager.get_sync_interval/set_sync_interval, including
the SYNC_INTERVAL_LOCKED behavior.

core/config.py computes SYNC_INTERVAL_LOCKED once at import time from
os.environ, so the locked vs. unlocked scenarios need separate fresh
interpreters - a single pytest process can't re-import config.py with
different env vars. Each scenario below runs as its own subprocess with a
temp DATA_DIR, so neither ever touches the real data/ directory.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

UNLOCKED_SCRIPT = f"""
import sys
sys.path.insert(0, {PROJECT_ROOT!r})
import core.config as config
import core.sync_manager as sync_manager
import core.cache as cache

assert config.SYNC_INTERVAL_LOCKED is False, "expected unlocked when SYNC_INTERVAL env var is unset"

assert sync_manager.get_sync_interval() == config.SYNC_INTERVAL

assert sync_manager.set_sync_interval(1800) is True
assert sync_manager.get_sync_interval() == 1800

overrides = cache.load_json(config.SETTINGS_FILE, default={{}})
assert overrides.get("sync_interval") == 1800
print("UNLOCKED_OK")
"""

LOCKED_SCRIPT = f"""
import sys
sys.path.insert(0, {PROJECT_ROOT!r})
import core.config as config
import core.sync_manager as sync_manager

assert config.SYNC_INTERVAL_LOCKED is True, "expected locked when SYNC_INTERVAL env var is set"
assert config.SYNC_INTERVAL == 7200

assert sync_manager.get_sync_interval() == 7200
assert sync_manager.set_sync_interval(999) is False
assert sync_manager.get_sync_interval() == 7200
print("LOCKED_OK")
"""


def test_unlocked_interval_round_trips(tmp_path):
    env = {"DATA_DIR": str(tmp_path), "PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [sys.executable, "-c", UNLOCKED_SCRIPT], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    assert "UNLOCKED_OK" in result.stdout


def test_locked_interval_refuses_changes(tmp_path):
    env = {
        "DATA_DIR": str(tmp_path),
        "SYNC_INTERVAL": "7200",
        "PATH": os.environ.get("PATH", ""),
    }
    result = subprocess.run(
        [sys.executable, "-c", LOCKED_SCRIPT], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    assert "LOCKED_OK" in result.stdout
