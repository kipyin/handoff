"""Helpers for loading project documentation files like README and RELEASE_NOTES."""

from __future__ import annotations

from .updater import _get_app_root


def read_markdown_from_app_root(name: str) -> str:
    r"""Return the contents of a markdown file located next to app.py.

    Args:
        name: Filename to load (for example, README.md or RELEASE_NOTES.md).

    Returns:
        File contents as a UTF-8 string, or a short placeholder message if the
        file cannot be found or read.

    """
    app_root = _get_app_root()
    path = app_root / name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"{name} not found at {path}."
    except OSError:
        return f"{name} could not be read from {path}."
