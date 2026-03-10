"""Unit tests for scripts.sizecheck path resolution and thresholds."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sizecheck as sizecheck_module


def _write_file_with_size(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_resolve_paths_collects_python_files_and_deduplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_resolve_paths should include .py files from dirs/files and dedupe overlaps."""
    monkeypatch.setattr(sizecheck_module, "ROOT", tmp_path)

    _write_file_with_size(tmp_path / "src" / "a.py", 10)
    _write_file_with_size(tmp_path / "src" / "nested" / "b.py", 10)
    _write_file_with_size(tmp_path / "scripts" / "tool.py", 10)
    _write_file_with_size(tmp_path / "src" / "ignore.txt", 10)

    resolved = sizecheck_module._resolve_paths(
        ["src", "src/a.py", "scripts/tool.py", "src/ignore.txt"]
    )

    assert set(resolved) == {
        tmp_path / "src" / "a.py",
        tmp_path / "src" / "nested" / "b.py",
        tmp_path / "scripts" / "tool.py",
    }


def test_run_sizecheck_reports_warnings_and_violations_relative_to_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_sizecheck should separate threshold warnings and hard-limit violations."""
    monkeypatch.setattr(sizecheck_module, "ROOT", tmp_path)

    _write_file_with_size(tmp_path / "src" / "ok.py", 50)
    _write_file_with_size(tmp_path / "src" / "warn.py", 90)
    _write_file_with_size(tmp_path / "src" / "too_big.py", 101)

    ok, violations, warnings = sizecheck_module.run_sizecheck(
        paths=None,
        default_path="src",
        max_bytes=100,
        warn_threshold=0.9,
    )

    assert ok is False
    assert violations == ["src/too_big.py: 101 bytes (max 100)"]
    assert warnings == ["src/warn.py: 90 bytes (90% of limit)"]


def test_run_sizecheck_explicit_paths_override_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit paths should be checked even when default_path would fail."""
    monkeypatch.setattr(sizecheck_module, "ROOT", tmp_path)

    _write_file_with_size(tmp_path / "src" / "too_big.py", 200)
    _write_file_with_size(tmp_path / "scripts" / "ok.py", 50)

    ok, violations, warnings = sizecheck_module.run_sizecheck(
        paths=["scripts"],
        default_path="src",
        max_bytes=100,
        warn_threshold=0.9,
    )

    assert ok is True
    assert violations == []
    assert warnings == []
