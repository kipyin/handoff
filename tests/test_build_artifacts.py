"""Tests for build scripts including key files and docs in archives."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.build_full as build_full_module
import scripts.build_patch as build_patch_module


def test_copy_docs_copies_readme_and_release_notes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_copy_docs copies README and release notes into the app build directory."""
    root = tmp_path
    readme = root / "README.md"
    release_notes = root / "RELEASE_NOTES.md"
    readme.write_text("readme", encoding="utf-8")
    release_notes.write_text("notes", encoding="utf-8")

    app_build_dir = root / "build" / "handoff"
    app_build_dir.mkdir(parents=True, exist_ok=True)

    # Mock shutil.copy2 to avoid disk I/O
    mock_copy = MagicMock()
    monkeypatch.setattr("shutil.copy2", mock_copy)
    monkeypatch.setattr(build_full_module, "ROOT", root)
    monkeypatch.setattr(build_full_module, "APP_BUILD_DIR", app_build_dir)

    build_full_module._copy_docs()

    # Verify the calls instead of checking the filesystem
    assert mock_copy.call_count == 2


def test_make_zip_includes_docs_and_core_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_make_zip records correct paths without actual zipping."""
    root = tmp_path
    build_root = root / "build"
    app_build_dir = build_root / "handoff"
    app_build_dir.mkdir(parents=True, exist_ok=True)

    # Documentation files that should be shipped.
    (app_build_dir / "README.md").write_text("readme", encoding="utf-8")
    (app_build_dir / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")

    # Application entrypoint.
    (app_build_dir / "app.py").write_text("print('hi')", encoding="utf-8")

    # Core package.
    pkg_dir = app_build_dir / "src" / "handoff"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    # Representative pages file.
    pages_dir = app_build_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "2_Projects.py").write_text("# page", encoding="utf-8")

    dist_root = root / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(build_full_module, "BUILD_ROOT", build_root)
    monkeypatch.setattr(build_full_module, "DIST_ROOT", dist_root)
    monkeypatch.setattr(build_full_module, "APP_BUILD_DIR", app_build_dir)

    # Mock ZipFile to prevent actual compression
    with patch("zipfile.ZipFile") as mock_zip:
        zip_instance = mock_zip.return_value.__enter__.return_value

        build_full_module._make_zip("handoff", "1.0.0")

        # Check that write was called for expected files
        written_names = set()
        for call in zip_instance.write.call_args_list:
            name = None
            if len(call.args) > 1:
                name = call.args[1]
            elif "arcname" in call.kwargs:
                name = call.kwargs["arcname"]
            else:
                name = call.args[0]
            written_names.add(str(name).replace("\\", "/"))

        # Paths are rooted under the versioned folder inside the zip.
        assert "handoff-1.0.0/README.md" in written_names
        assert "handoff-1.0.0/RELEASE_NOTES.md" in written_names
        assert "handoff-1.0.0/app.py" in written_names
        assert "handoff-1.0.0/src/handoff/__init__.py" in written_names
        assert "handoff-1.0.0/pages/2_Projects.py" in written_names


def test_build_patch_includes_docs_and_core_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_patch records correct paths without actual zipping or obfuscation."""
    root = tmp_path

    # Top-level documentation files (build_full._copy_docs reads from ROOT).
    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")

    build_app_dir = root / "build" / "handoff"
    build_app_dir.mkdir(parents=True, exist_ok=True)
    dist_root = root / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(build_patch_module, "ROOT", root)
    monkeypatch.setattr(build_patch_module, "BUILD_APP_DIR", build_app_dir)
    monkeypatch.setattr(build_patch_module, "DIST_ROOT", dist_root)

    # Stub regeneration so we don't run PyArmor or touch the real project.
    def _fake_copy_app_code() -> None:
        (build_app_dir / "app.py").write_text("print('hi')", encoding="utf-8")
        (build_app_dir / "src_plain" / "handoff").mkdir(parents=True, exist_ok=True)
        (build_app_dir / "src_plain" / "handoff" / "__init__.py").write_text(
            "x = 1", encoding="utf-8"
        )

    def _fake_obfuscate(*, dry_run: bool = False) -> None:
        (build_app_dir / "src" / "handoff").mkdir(parents=True, exist_ok=True)
        (build_app_dir / "src" / "handoff" / "__init__.py").write_text("x = 1", encoding="utf-8")

    def _fake_copy_docs() -> None:
        (build_app_dir / "README.md").write_text("readme", encoding="utf-8")
        (build_app_dir / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")

    monkeypatch.setattr(build_full_module, "_copy_app_code", _fake_copy_app_code)
    monkeypatch.setattr(build_full_module, "_obfuscate_app_code_with_pyarmor", _fake_obfuscate)
    monkeypatch.setattr(build_full_module, "_copy_docs", _fake_copy_docs)

    with patch("zipfile.ZipFile") as mock_zip:
        zip_instance = mock_zip.return_value.__enter__.return_value

        build_patch_module.build_patch(include_pages=False)

        # Verify VERSION was written via writestr
        written_via_writestr = {
            str(call.args[0]).replace("\\", "/") for call in zip_instance.writestr.call_args_list
        }
        assert "VERSION" in written_via_writestr

        # Verify other files were written via write
        written_via_write = set()
        for call in zip_instance.write.call_args_list:
            name = None
            if len(call.args) > 1:
                name = call.args[1]
            elif "arcname" in call.kwargs:
                name = call.kwargs["arcname"]
            else:
                name = call.args[0]
            written_via_write.add(str(name).replace("\\", "/"))

        assert "README.md" in written_via_write
        assert "RELEASE_NOTES.md" in written_via_write
        assert "app.py" in written_via_write
        assert "src/handoff/__init__.py" in written_via_write


def test_obfuscate_retries_with_trial_fallback_for_out_of_license(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-license retries with excludes and copies plain fallback modules."""
    app_build_dir = tmp_path / "build" / "handoff"
    src_plain_dir = app_build_dir / "src_plain" / "handoff"
    src_plain_dir.mkdir(parents=True, exist_ok=True)
    (src_plain_dir / "__init__.py").write_text("x = 1", encoding="utf-8")
    plain_data = src_plain_dir / "data.py"
    plain_data.write_text("DATA = 1", encoding="utf-8")

    monkeypatch.setattr(build_full_module, "APP_BUILD_DIR", app_build_dir)
    monkeypatch.setattr(build_full_module, "SRC_PLAIN_DIR", app_build_dir / "src_plain")
    monkeypatch.setattr(
        build_full_module,
        "PYARMOR_TRIAL_EXCLUDE_FILES",
        (Path("handoff/data.py"),),
    )
    monkeypatch.setattr("shutil.which", lambda name: "/tmp/pyarmor" if name == "pyarmor" else None)

    calls: list[list[str]] = []

    def _fake_run(
        cmd: list[str],
        *,
        check: bool,
        cwd: Path,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        assert cwd == app_build_dir / "src_plain"
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(
                2,
                cmd,
                stderr="ERROR out of license",
            )
        obf_pkg = app_build_dir / "src" / "handoff"
        obf_pkg.mkdir(parents=True, exist_ok=True)
        (obf_pkg / "__init__.py").write_text("# obfuscated", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    build_full_module._obfuscate_app_code_with_pyarmor()

    assert len(calls) == 2
    assert "--exclude" in calls[1]
    assert "handoff/data.py" in calls[1]
    copied_data = app_build_dir / "src" / "handoff" / "data.py"
    assert copied_data.read_text(encoding="utf-8") == "DATA = 1"
    assert not (app_build_dir / "src_plain").exists()


def test_obfuscate_raises_runtime_error_for_non_license_pyarmor_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-license PyArmor failures raise RuntimeError immediately."""
    app_build_dir = tmp_path / "build" / "handoff"
    src_plain_dir = app_build_dir / "src_plain" / "handoff"
    src_plain_dir.mkdir(parents=True, exist_ok=True)
    (src_plain_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    monkeypatch.setattr(build_full_module, "APP_BUILD_DIR", app_build_dir)
    monkeypatch.setattr(build_full_module, "SRC_PLAIN_DIR", app_build_dir / "src_plain")
    monkeypatch.setattr("shutil.which", lambda name: "/tmp/pyarmor" if name == "pyarmor" else None)

    def _fake_run(
        cmd: list[str],
        *,
        check: bool,
        cwd: Path,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(2, cmd, stderr="unexpected failure")

    monkeypatch.setattr("subprocess.run", _fake_run)

    with pytest.raises(RuntimeError, match="PyArmor failed while obfuscating application code"):
        build_full_module._obfuscate_app_code_with_pyarmor()
