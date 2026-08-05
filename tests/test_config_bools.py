"""Regression test for STARTUP_SCAN's env-var boolean coercion.

core/config.py computes STARTUP_SCAN once at import time from os.environ, so
each scenario needs a fresh interpreter (same reasoning/pattern as
test_settings.py's SYNC_INTERVAL_LOCKED tests) - a bare truthy check on the
env var string would make STARTUP_SCAN=false truthy (non-empty string) and
never actually disable the startup scan, which is exactly the bug this
guards against.

Each scenario also runs against an isolated copy of core/config.py in its
own tmp directory with no config.yaml/.env sibling - core/config.py resolves
its own project root from its own file location, so importing the real copy
directly would pick up whatever real (gitignored) config.yaml happens to
exist on the machine running the test, making the "unset" scenario
non-deterministic between a dev machine and CI.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REAL_CONFIG_PY = Path(__file__).resolve().parent.parent / "core" / "config.py"

CHECK_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import core.config as config
assert config.STARTUP_SCAN is {expected}, f"expected {expected}, got {{config.STARTUP_SCAN!r}}"
print("OK")
"""


def _run_isolated(tmp_path, startup_scan_env, expected: bool):
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("")
    shutil.copy(REAL_CONFIG_PY, core_dir / "config.py")

    env = {"PATH": os.environ.get("PATH", "")}
    if startup_scan_env is not None:
        env["STARTUP_SCAN"] = startup_scan_env

    result = subprocess.run(
        [sys.executable, "-c", CHECK_SCRIPT.format(root=str(tmp_path), expected=expected)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_startup_scan_false_string_is_falsy(tmp_path):
    _run_isolated(tmp_path, "false", False)


def test_startup_scan_true_string_is_truthy(tmp_path):
    _run_isolated(tmp_path, "true", True)


def test_startup_scan_zero_string_is_falsy(tmp_path):
    _run_isolated(tmp_path, "0", False)


def test_startup_scan_unset_defaults_true(tmp_path):
    _run_isolated(tmp_path, None, True)
