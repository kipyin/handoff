"""Tests for documentation helpers."""

from __future__ import annotations

import os
from pathlib import Path

from handoff.docs import read_markdown_from_app_root


def test_read_markdown_from_app_root_finds_release_notes_from_any_cwd(tmp_path: Path) -> None:
    """read_markdown_from_app_root should resolve paths relative to app root, not CWD."""
    # Change working directory away from the project root to ensure we don't
    # accidentally rely on the current process CWD.
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        content = read_markdown_from_app_root("RELEASE_NOTES.md")
    finally:
        os.chdir(original_cwd)

    assert "Release notes" in content
