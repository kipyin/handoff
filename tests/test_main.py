"""Tests for python -m handoff entrypoint (__main__.py)."""

from __future__ import annotations

import contextlib
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
