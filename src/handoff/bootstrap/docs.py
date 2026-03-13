"""Helpers for loading project documentation files like README and RELEASE_NOTES."""

from __future__ import annotations

import re

from .paths import get_app_root

_get_app_root = get_app_root


def read_markdown_from_app_root(name: str) -> str:
    """Return the contents of a markdown file located next to app.py.

    Returns file contents as a UTF-8 string, or a short placeholder message if the
    file is not found or an I/O error occurs while reading.
    """
    app_root = _get_app_root()
    path = app_root / name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"{name} not found at {path}."
    except OSError:
        return f"{name} could not be read from {path}."


def get_readme_intro() -> str:
    """Return the introductory paragraphs from README.md (before the second ``##`` heading).

    If the README cannot be loaded, the placeholder message from
    `read_markdown_from_app_root` is returned instead.
    """
    content = read_markdown_from_app_root("README.md")
    parts = re.split(r"^## ", content, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 2:
        return content.strip()
    intro = parts[1]
    _, _, body = intro.partition("\n")
    return body.strip()
