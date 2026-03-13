"""Tests for handoff.bootstrap.config (Streamlit env defaults).

Config is applied at import time. We run assertions in a subprocess so the
test runner's environment is not mutated and tests remain order-independent.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_config_sets_streamlit_env_defaults() -> None:
    """Importing handoff.bootstrap.config sets STREAMLIT_* env vars when not already set."""
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
import handoff.bootstrap.config  # noqa: F401
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
