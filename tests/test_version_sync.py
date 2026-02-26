"""Ensure app.py version stays aligned with pyproject metadata."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app.py"
PYPROJECT = ROOT / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Return the package version from pyproject.toml."""
    with PYPROJECT.open("rb") as fp:
        pyproject_data = tomllib.load(fp)
    return pyproject_data["project"]["version"]


def _read_app_version_constant() -> str:
    """Extract APP_VERSION literal from app.py."""
    app_text = APP_PY.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"\s*$', app_text, re.MULTILINE)
    assert match is not None, "APP_VERSION constant is missing in app.py"
    return match.group(1)


def test_app_version_matches_pyproject() -> None:
    """app.py APP_VERSION should match pyproject [project].version."""
    assert _read_app_version_constant() == _read_pyproject_version()
