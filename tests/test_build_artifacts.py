"""Tests for build scripts including key files and docs in archives."""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

import scripts.build_zip as build_zip_module
import scripts.build_patch as build_patch_module
import scripts.build_obfuscated_patch as build_obfuscated_patch_module


def test_copy_docs_copies_readme_and_release_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_copy_docs copies README and release notes into the app build directory."""
    root = tmp_path
    readme = root / "README.md"
    release_notes = root / "RELEASE_NOTES.md"
    readme.write_text("readme", encoding="utf-8")
    release_notes.write_text("notes", encoding="utf-8")

    app_build_dir = root / "build" / "todo-app"
    app_build_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(build_zip_module, "ROOT", root)
    monkeypatch.setattr(build_zip_module, "APP_BUILD_DIR", app_build_dir)

    build_zip_module._copy_docs()

    assert (app_build_dir / "README.md").is_file()
    assert (app_build_dir / "RELEASE_NOTES.md").is_file()


def test_make_zip_includes_docs_and_core_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_make_zip includes docs, app.py, core package, and pages."""
    root = tmp_path
    build_root = root / "build"
    app_build_dir = build_root / "todo-app"
    app_build_dir.mkdir(parents=True, exist_ok=True)

    # Documentation files that should be shipped.
    (app_build_dir / "README.md").write_text("readme", encoding="utf-8")
    (app_build_dir / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")

    # Application entrypoint.
    (app_build_dir / "app.py").write_text("print('hi')", encoding="utf-8")

    # Core package.
    pkg_dir = app_build_dir / "src" / "todo_app"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    # Representative pages file.
    pages_dir = app_build_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "2_Projects.py").write_text("# page", encoding="utf-8")

    dist_root = root / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(build_zip_module, "BUILD_ROOT", build_root)
    monkeypatch.setattr(build_zip_module, "DIST_ROOT", dist_root)
    monkeypatch.setattr(build_zip_module, "APP_BUILD_DIR", app_build_dir)

    zip_path = build_zip_module._make_zip("todo-app", "1.0.0")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())

    # Paths are relative to BUILD_ROOT, so they are prefixed with "todo-app/".
    assert "todo-app/README.md" in names
    assert "todo-app/RELEASE_NOTES.md" in names
    assert "todo-app/app.py" in names
    assert "todo-app/src/todo_app/__init__.py" in names
    assert "todo-app/pages/2_Projects.py" in names


def test_build_patch_includes_docs_and_core_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build_patch writes docs, app.py, and core package into the patch zip."""
    root = tmp_path
    monkeypatch.setattr(build_patch_module, "ROOT", root)
    dist_root = root / "dist"
    monkeypatch.setattr(build_patch_module, "DIST_ROOT", dist_root)

    # Project root files.
    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")
    (root / "app.py").write_text("print('hi')", encoding="utf-8")

    # Minimal package structure under src/.
    pkg_dir = root / "src" / "todo_app"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    zip_path = build_patch_module.build_patch(include_pages=False)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())

    assert "VERSION" in names
    assert "README.md" in names
    assert "RELEASE_NOTES.md" in names
    assert "app.py" in names
    assert "src/todo_app/__init__.py" in names


def test_build_obfuscated_patch_includes_docs_and_core_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build_obfuscated_patch writes docs, app.py, and core package into the patch zip."""
    root = tmp_path

    # Top-level documentation files.
    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "RELEASE_NOTES.md").write_text("notes", encoding="utf-8")

    build_app_dir = root / "build" / "todo-app"
    src_dir = build_app_dir / "src"
    todo_app_dir = src_dir / "todo_app"
    todo_app_dir.mkdir(parents=True, exist_ok=True)

    # Minimal obfuscated package layout (contents are irrelevant for this test).
    (todo_app_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    # app.py that should be included when present in the build tree.
    build_app_dir.mkdir(parents=True, exist_ok=True)
    (build_app_dir / "app.py").write_text("print('hi')", encoding="utf-8")

    dist_root = root / "dist"

    monkeypatch.setattr(build_obfuscated_patch_module, "ROOT", root)
    monkeypatch.setattr(build_obfuscated_patch_module, "BUILD_APP_DIR", build_app_dir)
    monkeypatch.setattr(build_obfuscated_patch_module, "DIST_ROOT", dist_root)

    zip_path = build_obfuscated_patch_module.build_obfuscated_patch(include_pages=False)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())

    assert "VERSION" in names
    assert "README.md" in names
    assert "RELEASE_NOTES.md" in names
    assert "app.py" in names
    assert "src/todo_app/__init__.py" in names

