"""Ensure version module stays aligned with pyproject metadata."""

from __future__ import annotations

import tomllib
from pathlib import Path

from handoff.version import __version__

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"


def _read_pyproject_version() -> str:
    """Return the package version from pyproject.toml."""
    with PYPROJECT.open("rb") as fp:
        pyproject_data = tomllib.load(fp)
    return pyproject_data["project"]["version"]


def _read_uv_lock_handoff_version() -> str:
    """Return the editable handoff package version from uv.lock."""
    with UV_LOCK.open("rb") as fp:
        uv_lock_data = tomllib.load(fp)

    for package in uv_lock_data.get("package", []):
        if package.get("name") != "handoff":
            continue
        if package.get("source", {}).get("editable") == ".":
            return package["version"]

    raise AssertionError('Could not find editable package "handoff" in uv.lock.')


def test_version_module_matches_pyproject() -> None:
    """handoff.version.__version__ should match pyproject [project].version."""
    assert __version__ == _read_pyproject_version()


def test_uv_lock_handoff_version_matches_pyproject() -> None:
    """uv.lock editable handoff version should match pyproject [project].version."""
    assert _read_uv_lock_handoff_version() == _read_pyproject_version()
