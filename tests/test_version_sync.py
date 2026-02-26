"""Ensure version module stays aligned with pyproject metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path

from todo_app.version import __version__

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Return the package version from pyproject.toml."""
    with PYPROJECT.open("rb") as fp:
        pyproject_data = tomllib.load(fp)
    return pyproject_data["project"]["version"]


def test_version_module_matches_pyproject() -> None:
    """todo_app.version.__version__ should match pyproject [project].version."""
    assert __version__ == _read_pyproject_version()
