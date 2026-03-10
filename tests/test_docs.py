"""Tests for documentation helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from handoff.docs import get_readme_intro, read_markdown_from_app_root


def test_read_markdown_from_app_root_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """read_markdown_from_app_root returns a message when the file does not exist."""
    monkeypatch.setattr("handoff.docs._get_app_root", lambda: tmp_path)
    result = read_markdown_from_app_root("Nonexistent.md")
    assert "not found" in result
    assert "Nonexistent.md" in result


def test_read_markdown_from_app_root_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read_markdown_from_app_root returns a message when read raises OSError."""

    def _read_text_raise(*args: object, **kwargs: object) -> str:
        raise OSError("Permission denied")

    monkeypatch.setattr("pathlib.Path.read_text", _read_text_raise)
    result = read_markdown_from_app_root("README.md")
    assert "could not be read" in result
    assert "README.md" in result


def test_cached_markdown_caches_and_calls_read_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """pages.about._cached_markdown caches result and reads each name once."""
    from handoff.pages.about import _cached_markdown

    _cached_markdown.clear()

    read_calls: list[str] = []

    def track_read(name: str) -> str:
        read_calls.append(name)
        return f"Content of {name}"

    monkeypatch.setattr("handoff.pages.about.read_markdown_from_app_root", track_read)

    first = _cached_markdown("README.md")
    second = _cached_markdown("README.md")
    assert first == second == "Content of {name}".format(name="README.md")
    assert read_calls == ["README.md"]
    _cached_markdown("RELEASE_NOTES.md")
    assert read_calls == ["README.md", "RELEASE_NOTES.md"]


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


def test_get_readme_intro_extracts_first_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_readme_intro returns text between the first and second ## headings."""
    readme = "## MyApp\n\nFirst paragraph.\n\nSecond paragraph.\n\n## Next Section\n\nMore."
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    monkeypatch.setattr("handoff.docs._get_app_root", lambda: tmp_path)
    result = get_readme_intro()
    assert "First paragraph." in result
    assert "Second paragraph." in result
    assert "Next Section" not in result


def test_get_readme_intro_real() -> None:
    """get_readme_intro returns non-empty text from the real README."""
    result = get_readme_intro()
    assert len(result) > 20
    lowered = result.lower()
    assert "not found" not in lowered
    assert "could not be read" not in lowered
