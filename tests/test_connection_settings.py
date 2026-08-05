"""Tests for the Sonarr/qBittorrent connection settings (SONARR_URL,
QB_URL, etc.) - a direct extension of the SYNC_INTERVAL_LOCKED pattern to
six more fields, all sharing the same data/settings.json override file.

core/config.py computes each *_LOCKED flag once at import time from
os.environ, so - same reasoning as test_settings.py - each scenario needs a
fresh interpreter with a temp DATA_DIR, never touching the real data/
directory.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Proves the *_LOCKED mechanism generalizes to a new field (sonarr_url),
# not just sync_interval - mirrors test_settings.py's LOCKED_SCRIPT.
LOCKED_SCRIPT = f"""
import sys
sys.path.insert(0, {PROJECT_ROOT!r})
import core.config as config
import core.sync_manager as sync_manager

assert config.SONARR_URL_LOCKED is True, "expected locked when SONARR_URL env var is set"
assert config.SONARR_URL == "http://locked-sonarr:8989"

assert sync_manager.get_sonarr_url() == "http://locked-sonarr:8989"
assert sync_manager.set_sonarr_url("http://attacker:9999") is False
assert sync_manager.get_sonarr_url() == "http://locked-sonarr:8989"
print("LOCKED_OK")
"""

# Sets three different fields (two connection settings + the pre-existing
# sync_interval) in the same settings.json and confirms none of them
# clobber each other - new real risk now that six more keys share one file.
MULTI_FIELD_SCRIPT = f"""
import sys
sys.path.insert(0, {PROJECT_ROOT!r})
import core.config as config
import core.sync_manager as sync_manager
import core.cache as cache

assert sync_manager.set_sonarr_url("http://my-sonarr:8989") is True
assert sync_manager.set_qb_user("my-qb-user") is True
assert sync_manager.set_sync_interval(1800) is True

assert sync_manager.get_sonarr_url() == "http://my-sonarr:8989"
assert sync_manager.get_qb_user() == "my-qb-user"
assert sync_manager.get_sync_interval() == 1800

overrides = cache.load_json(config.SETTINGS_FILE, default={{}})
assert overrides.get("sonarr_url") == "http://my-sonarr:8989"
assert overrides.get("qb_user") == "my-qb-user"
assert overrides.get("sync_interval") == 1800
print("MULTI_FIELD_OK")
"""


def test_locked_sonarr_url_refuses_changes(tmp_path):
    env = {
        "DATA_DIR": str(tmp_path),
        "SONARR_URL": "http://locked-sonarr:8989",
        "PATH": os.environ.get("PATH", ""),
    }
    result = subprocess.run(
        [sys.executable, "-c", LOCKED_SCRIPT], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    assert "LOCKED_OK" in result.stdout


def test_multiple_fields_do_not_clobber_each_other(tmp_path):
    env = {"DATA_DIR": str(tmp_path), "PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [sys.executable, "-c", MULTI_FIELD_SCRIPT], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    assert "MULTI_FIELD_OK" in result.stdout
