"""Tests for python -m handoff entrypoint (__main__.py)."""

from __future__ import annotations

import contextlib
import os
import runpy
import sys
from unittest.mock import MagicMock, patch


def test_main_runs_streamlit_with_app_py() -> None:
    """python -m handoff runs streamlit run app.py via subprocess and exits with its returncode."""
    subprocess_run = MagicMock(return_value=MagicMock(returncode=0))
    exit_calls: list[int] = []

    def capture_exit(code: int) -> None:
        exit_calls.append(code)
        raise SystemExit(code)

    # Patch where __main__ looks them up (it does "import subprocess" / uses sys.exit).
    with (
        patch("subprocess.run", subprocess_run),
        patch("sys.exit", side_effect=capture_exit),
        contextlib.suppress(SystemExit),
    ):
        runpy.run_module("handoff", run_name="__main__")

    assert len(exit_calls) == 1
    assert exit_calls[0] == 0
    subprocess_run.assert_called_once()
    call_args = subprocess_run.call_args
    assert call_args[0][0] == [sys.executable, "-m", "streamlit", "run", "app.py"]
    assert call_args[1]["env"] is not None  # env=os.environ


def test_main_applies_bootstrap_config_defaults_to_subprocess_env() -> None:
    """Entry-point import should apply Streamlit defaults before spawning subprocess."""
    captured_env: dict[str, str] | None = None
    exit_calls: list[int] = []

    def capture_run(*args: object, **kwargs: object) -> MagicMock:
        nonlocal captured_env
        env = kwargs.get("env")
        if env is not None:
            captured_env = dict(env)
        return MagicMock(returncode=0)

    def capture_exit(code: int) -> None:
        exit_calls.append(code)
        raise SystemExit(code)

    streamlit_defaults = {
        "STREAMLIT_CLIENT_SHOW_ERROR_DETAILS": "none",
        "STREAMLIT_CLIENT_TOOLBAR_MODE": "viewer",
        "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION": "false",
        "STREAMLIT_CLIENT_SHOW_ERROR_LINKS": "false",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    }
    old_values = {key: os.environ.get(key) for key in streamlit_defaults}
    old_config_module = sys.modules.get("handoff.bootstrap.config")

    try:
        for key in streamlit_defaults:
            os.environ.pop(key, None)
        # Force a fresh import so config side effects are exercised deterministically.
        sys.modules.pop("handoff.bootstrap.config", None)

        with (
            patch("subprocess.run", side_effect=capture_run),
            patch("sys.exit", side_effect=capture_exit),
            contextlib.suppress(SystemExit),
        ):
            runpy.run_module("handoff", run_name="__main__")
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if old_config_module is None:
            sys.modules.pop("handoff.bootstrap.config", None)
        else:
            sys.modules["handoff.bootstrap.config"] = old_config_module

    assert exit_calls == [0]
    assert captured_env is not None, "subprocess.run should have been called with env"
    for key, expected in streamlit_defaults.items():
        assert captured_env[key] == expected
