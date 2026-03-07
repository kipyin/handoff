"""Tests for the logging configuration module."""

from __future__ import annotations

from pathlib import Path

from handoff.logging import _get_logs_dir


def test_get_logs_dir_returns_path_and_creates_it() -> None:
    """_get_logs_dir returns a Path that exists."""
    logs_dir = _get_logs_dir()
    assert isinstance(logs_dir, Path)
    assert logs_dir.exists()
    assert logs_dir.name == "logs"
