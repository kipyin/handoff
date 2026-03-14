"""Tests for Streamlit runtime config (interfaces.streamlit.runtime_config).

Config is applied at import time. We run assertions in a subprocess so the
test runner's environment is not mutated and tests remain order-independent.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_config_sets_streamlit_env_defaults() -> None:
    """Importing runtime_config sets STREAMLIT_* env vars when not already set."""
    code = """
import os
# Simulate clean env for the keys we set (so setdefault takes effect).
for key in (
    "STREAMLIT_CLIENT_SHOW_ERROR_DETAILS",
    "STREAMLIT_CLIENT_TOOLBAR_MODE",
    "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION",
    "STREAMLIT_CLIENT_SHOW_ERROR_LINKS",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS",
):
    os.environ.pop(key, None)
import handoff.interfaces.streamlit.runtime_config  # noqa: F401
assert os.environ.get("STREAMLIT_CLIENT_SHOW_ERROR_DETAILS") == "none"
assert os.environ.get("STREAMLIT_CLIENT_TOOLBAR_MODE") == "viewer"
assert os.environ.get("STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION") == "false"
assert os.environ.get("STREAMLIT_CLIENT_SHOW_ERROR_LINKS") == "false"
assert os.environ.get("STREAMLIT_BROWSER_GATHER_USAGE_STATS") == "false"
"""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")


def test_runtime_config_respects_already_set_env_vars() -> None:
    """Importing runtime_config does not override vars already in os.environ."""
    code = """
import os
# Pre-set one of the vars to a custom value.
os.environ["STREAMLIT_CLIENT_SHOW_ERROR_DETAILS"] = "all"
os.environ["STREAMLIT_CLIENT_TOOLBAR_MODE"] = "minimal"
import handoff.interfaces.streamlit.runtime_config  # noqa: F401
# Should not override already-set values.
assert os.environ.get("STREAMLIT_CLIENT_SHOW_ERROR_DETAILS") == "all"
assert os.environ.get("STREAMLIT_CLIENT_TOOLBAR_MODE") == "minimal"
# Should set defaults for unset vars.
assert os.environ.get("STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION") == "false"
"""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
