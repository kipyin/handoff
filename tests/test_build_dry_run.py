"""Integration tests for build --dry-run (no PyArmor, no downloads, no archive)."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.build_full as build_full_module
import scripts.build_patch as build_patch_module
from handoff.version import __version__


def test_build_full_dry_run_creates_build_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build --full --dry-run runs copy/docs/launcher steps and creates expected files."""
    # Use a temp dir as project root to avoid polluting the real build/
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)

    build_full_module.main(platform="windows", dry_run=True)

    build_root = root / "build"
    assert build_root.exists()

    # build_full creates build/handoff-{version}; build_patch uses build/handoff.
    # We must check the versioned dir (where handoff.bat is written).
    app_dir = build_root / f"handoff-{__version__}"
    assert app_dir.is_dir()

    assert (app_dir / "app.py").exists()
    assert (app_dir / "README.md").exists()
    assert (app_dir / "RELEASE_NOTES.md").exists()
    assert (app_dir / "src" / "handoff").exists()
    # Windows dry-run writes handoff.bat
    assert (app_dir / "handoff.bat").exists()
    bat_content = (app_dir / "handoff.bat").read_text(encoding="utf-8")
    assert 'xcopy /E /Y "%SCRIPT_DIR%update\\*" "%SCRIPT_DIR%" >nul' in bat_content
    # If xcopy fails, launcher must keep update/ and abort.
    assert "if errorlevel 1 (" in bat_content
    assert "staged files are still in .\\update\\ for retry" in bat_content.lower()
    assert "exit /b 1" in bat_content


def test_build_full_dry_run_mac_creates_sh_launcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build --full --platform mac --dry-run writes handoff.sh."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)

    build_full_module.main(platform="mac", dry_run=True)

    build_root = root / "build"
    app_dir = build_root / f"handoff-{__version__}"
    assert app_dir.is_dir()

    assert (app_dir / "handoff.sh").exists()
    content = (app_dir / "handoff.sh").read_text()
    assert "PYTHONPATH" in content
    assert "python" in content


def test_build_patch_dry_run_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build --patch --dry-run runs copy/obfuscate-stub/docs and returns path."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    expected_path = root / "dist" / f"handoff-{__version__}-patch.zip"
    if expected_path.exists():
        expected_path.unlink()

    path = build_patch_module.build_patch(dry_run=True)

    assert path is not None
    assert path.name.endswith("-patch.zip")
    assert path == expected_path
    # Dry run does not create the zip
    assert not path.exists()

    # Build structure should exist under build/handoff
    build_app = root / "build" / "handoff"
    assert (build_app / "src" / "handoff").exists()
    assert (build_app / "app.py").exists()
