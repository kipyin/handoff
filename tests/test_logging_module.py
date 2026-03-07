"""Tests for the logging configuration module."""

from __future__ import annotations

from pathlib import Path

import pytest

from handoff.logging import _get_logs_dir


def test_get_logs_dir_returns_path_and_creates_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_logs_dir returns a Path under the data dir and creates it."""
    monkeypatch.setattr("handoff.logging.user_data_dir", lambda app, author: str(tmp_path))
    logs_dir = _get_logs_dir()
    assert isinstance(logs_dir, Path)
    assert logs_dir.exists()
    assert logs_dir == tmp_path / "logs"
    assert logs_dir.name == "logs"
