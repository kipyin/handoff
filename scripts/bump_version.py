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
VERSION_PATH = ROOT / "src" / "handoff" / "version.py"


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


def _replace_version_constant(version_text: str, new_version: str) -> str:
    """Replace __version__ literal in the version module."""
    pattern = r'(?m)^(__version__\s*=\s*)"[^"]*"\s*$'
    updated, count = re.subn(pattern, rf'\1"{new_version}"', version_text)
    if count != 1:
        raise RuntimeError("Could not find a unique __version__ assignment in version.py.")
    return updated


def bump_version(new_version: str) -> None:
    """Update pyproject and version module to the given value.

    Args:
        new_version: Target version string (for example, ``2026.3.0``).
    """
    pyproject_original = PYPROJECT_PATH.read_text(encoding="utf-8")
    version_original = VERSION_PATH.read_text(encoding="utf-8")

    pyproject_updated = _replace_project_version(pyproject_original, new_version)
    version_updated = _replace_version_constant(version_original, new_version)

    PYPROJECT_PATH.write_text(pyproject_updated, encoding="utf-8")
    VERSION_PATH.write_text(version_updated, encoding="utf-8")
    print(f"Updated version to {new_version} in pyproject.toml and src/handoff/version.py")


def main() -> None:
    """CLI entrypoint for synchronizing version strings."""
    parser = argparse.ArgumentParser(
        description="Bump version in pyproject.toml and src/handoff/version.py together.",
    )
    parser.add_argument(
        "version",
        type=_validate_version,
        help="New version string (e.g. 2026.3.0)",
    )
    args = parser.parse_args()
    bump_version(args.version)


if __name__ == "__main__":
    main()
