"""Update app and package version together.

Usage:
    uv run python scripts/bump_version.py 2026.3.0
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
APP_PATH = ROOT / "app.py"


def _validate_version(value: str) -> str:
    """Validate a version argument.

    Args:
        value: User-provided version string.

    Returns:
        The normalized version string.

    Raises:
        argparse.ArgumentTypeError: If the version is empty or contains whitespace.
    """
    normalized = value.strip()
    if not normalized or any(ch.isspace() for ch in normalized):
        raise argparse.ArgumentTypeError("Version must be non-empty and contain no whitespace.")
    return normalized


def _replace_project_version(pyproject_text: str, new_version: str) -> str:
    """Replace `[project]` version in pyproject content.

    Args:
        pyproject_text: Original TOML content.
        new_version: Target version.

    Returns:
        Updated TOML content.

    Raises:
        RuntimeError: If a `[project] version = ...` entry cannot be found.
    """
    lines = pyproject_text.splitlines()
    in_project_section = False
    replaced = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project_section = stripped == "[project]"
            continue
        if in_project_section and stripped.startswith("version"):
            lines[index] = re.sub(r'^(\s*version\s*=\s*)"[^"]*"\s*$', rf'\1"{new_version}"', line)
            replaced = True
            break

    if not replaced:
        raise RuntimeError("Could not find `[project]` `version = ...` in pyproject.toml.")
    return "\n".join(lines) + "\n"


def _replace_app_version(app_text: str, new_version: str) -> str:
    """Replace APP_VERSION literal in app.py."""
    pattern = r'(?m)^(APP_VERSION\s*=\s*)"[^"]*"\s*$'
    updated, count = re.subn(pattern, rf'\1"{new_version}"', app_text)
    if count != 1:
        raise RuntimeError("Could not find a unique APP_VERSION assignment in app.py.")
    return updated


def main() -> None:
    """CLI entrypoint for synchronizing version strings."""
    parser = argparse.ArgumentParser(
        description="Bump version in pyproject.toml and app.py together.",
    )
    parser.add_argument(
        "version",
        type=_validate_version,
        help="New version string (e.g. 2026.3.0)",
    )
    args = parser.parse_args()

    pyproject_original = PYPROJECT_PATH.read_text(encoding="utf-8")
    app_original = APP_PATH.read_text(encoding="utf-8")

    pyproject_updated = _replace_project_version(pyproject_original, args.version)
    app_updated = _replace_app_version(app_original, args.version)

    PYPROJECT_PATH.write_text(pyproject_updated, encoding="utf-8")
    APP_PATH.write_text(app_updated, encoding="utf-8")
    print(f"Updated version to {args.version} in pyproject.toml and app.py")


if __name__ == "__main__":
    main()
