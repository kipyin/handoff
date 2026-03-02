"""Tests for the in-app updater helpers."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

from handoff.updater import (
    _clear_pycache,
    _format_snapshot_label,
    _iter_backup_snapshots,
    _restore_backup_snapshot,
    apply_patch_zip,
    apply_staged_update,
    extract_patch_to_staging,
    stage_patch_with_backup,
    stage_restore_from_snapshot,
)


def _build_patch_zip_bytes(
    files: dict[str, bytes],
    *,
    version: str | None = None,
) -> bytes:
    """Return bytes for a patch zip with optional VERSION marker."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        if version is not None:
            zf.writestr("VERSION", version)
        for name, content in files.items():
            zf.writestr(name, content)
    buffer.seek(0)
    return buffer.getvalue()


def test_apply_patch_zip_applies_allowed_paths_and_creates_backup(tmp_path: Path) -> None:
    """Allowed paths are applied and a backup of previous contents is created."""
    app_root = tmp_path
    app_file = app_root / "app.py"
    src_dir = app_root / "src"
    src_dir.mkdir()
    src_file = src_dir / "module.py"

    app_file.write_text("old app", encoding="utf-8")
    src_file.write_text("old src", encoding="utf-8")

    zip_bytes = _build_patch_zip_bytes(
        {
            "app.py": b"new app",
            "src/module.py": b"new src",
            "ignored.txt": b"should be ignored",
        },
        version="2026.2.99",
    )

    message = apply_patch_zip(BytesIO(zip_bytes), app_root=app_root)
    assert "Target version: 2026.2.99" in message

    # Updated contents are written to the app root.
    assert app_file.read_text(encoding="utf-8") == "new app"
    assert src_file.read_text(encoding="utf-8") == "new src"
    # Disallowed path is ignored.
    assert not (app_root / "ignored.txt").exists()

    # A timestamped backup directory exists and contains the previous contents.
    backup_root = app_root / "backup"
    backups = [path for path in backup_root.iterdir() if path.is_dir()]
    assert backups, "Expected at least one backup directory"
    # There should be exactly one snapshot for this test.
    snapshot = backups[0]
    assert (snapshot / "app.py").read_text(encoding="utf-8") == "old app"
    assert (snapshot / "src" / "module.py").read_text(encoding="utf-8") == "old src"


def test_extract_patch_to_staging_writes_to_update_dir(tmp_path: Path) -> None:
    """extract_patch_to_staging extracts zip into app_root/update/ and leaves app root unchanged."""
    app_root = tmp_path
    app_file = app_root / "app.py"
    app_file.write_text("old app", encoding="utf-8")

    zip_bytes = _build_patch_zip_bytes(
        {"app.py": b"new app", "src/module.py": b"new src"},
        version="2026.2.99",
    )
    message = extract_patch_to_staging(BytesIO(zip_bytes), app_root=app_root)

    assert "2026.2.99" in message
    assert "run.bat" in message
    # Staging dir contains new content.
    staging = app_root / "update"
    assert (staging / "app.py").read_text(encoding="utf-8") == "new app"
    assert (staging / "src" / "module.py").read_text(encoding="utf-8") == "new src"
    # App root is unchanged.
    assert app_file.read_text(encoding="utf-8") == "old app"


def test_stage_patch_with_backup_creates_backup_and_staging_leaves_app_root_unchanged(
    tmp_path: Path,
) -> None:
    """Verify stage_patch_with_backup backup, sentinel, and staging behaviour.

    It should create a backup, write the sentinel, and extract to update/ while
    leaving the app root unchanged.
    """
    app_root = tmp_path
    app_file = app_root / "app.py"
    app_file.write_text("old app", encoding="utf-8")

    zip_bytes = _build_patch_zip_bytes(
        {"app.py": b"new app", "src/module.py": b"new src"},
        version="2026.2.99",
    )
    message = stage_patch_with_backup(
        BytesIO(zip_bytes),
        app_root=app_root,
        app_version="2026.3.1",
    )

    assert "2026.2.99" in message
    assert "run.bat" in message or "run.ps1" in message
    # Backup dir exists with version in name and contains previous app.py.
    backup_root = app_root / "backup"
    backups = [p for p in backup_root.iterdir() if p.is_dir()]
    assert len(backups) == 1
    assert backups[0].name.endswith("-version2026.3.1")
    assert (backups[0] / "app.py").read_text(encoding="utf-8") == "old app"
    # Sentinel written.
    sentinel = app_root / ".last_update_backup"
    sentinel_text = sentinel.read_text(encoding="utf-8")
    assert sentinel_text.strip().startswith("backup/")
    assert "version2026.3.1" in sentinel_text
    # Staging has new content.
    assert (app_root / "update" / "app.py").read_text(encoding="utf-8") == "new app"
    # App root unchanged (launcher will copy later).
    assert app_file.read_text(encoding="utf-8") == "old app"


def test_extract_patch_to_staging_no_applicable_files(tmp_path: Path) -> None:
    """extract_patch_to_staging returns message when zip has no allowed paths."""
    app_root = tmp_path
    zip_bytes = _build_patch_zip_bytes({"other/file.txt": b"content"})
    message = extract_patch_to_staging(BytesIO(zip_bytes), app_root=app_root)
    assert message == "No applicable files found in patch zip."
    assert not (app_root / "update").exists()


def test_apply_patch_zip_with_only_disallowed_paths_returns_message(tmp_path: Path) -> None:
    """Patch containing only disallowed paths results in a no-op message."""
    app_root = tmp_path
    zip_bytes = _build_patch_zip_bytes({"other/file.txt": b"content"})

    message = apply_patch_zip(BytesIO(zip_bytes), app_root=app_root)
    assert message == "No applicable files found in patch zip."
    assert not (app_root / "backup").exists()


def test_clear_pycache_removes_pycache_directories(tmp_path: Path) -> None:
    """_clear_pycache removes __pycache__ directories under the app root."""
    app_root = tmp_path
    top_pycache = app_root / "__pycache__"
    nested_pycache = app_root / "src" / "__pycache__"

    for directory in (top_pycache, nested_pycache):
        directory.mkdir(parents=True)
        (directory / "dummy.pyc").write_bytes(b"x")

    _clear_pycache(app_root)

    assert not top_pycache.exists()
    assert not nested_pycache.exists()


def test_iter_backup_snapshots_orders_newest_first(tmp_path: Path) -> None:
    """_iter_backup_snapshots returns snapshots sorted newest-first."""
    app_root = tmp_path
    backup_root = app_root / "backup"
    backup_root.mkdir()

    older = backup_root / "20260101-120000"
    newer = backup_root / "20260102-130000"
    older.mkdir()
    newer.mkdir()

    snapshots = _iter_backup_snapshots(app_root)
    assert snapshots == [newer, older]


def test_format_snapshot_label_supports_legacy_and_versioned_names() -> None:
    """_format_snapshot_label parses legacy and versioned backup folder names."""
    from pathlib import Path

    legacy = Path("backup/20260101-120000")
    assert _format_snapshot_label(legacy) == "2026-01-01 12:00:00"
    versioned = Path("backup/20260302-000612-version2026.3.1")
    label = _format_snapshot_label(versioned)
    assert "2026-03-02 00:06:12" in label
    assert "version 2026.3.1" in label


def test_stage_restore_from_snapshot_populates_update_and_leaves_app_root_unchanged(
    tmp_path: Path,
) -> None:
    """stage_restore_from_snapshot copies snapshot into update/; app root unchanged."""
    app_root = tmp_path
    snapshot = app_root / "backup" / "20260101-120000"
    snapshot.mkdir(parents=True)
    (snapshot / "app.py").write_text("from backup", encoding="utf-8")
    (snapshot / "src").mkdir()
    (snapshot / "src" / "module.py").write_text("from backup src", encoding="utf-8")

    (app_root / "app.py").write_text("current app", encoding="utf-8")
    (app_root / "src").mkdir(exist_ok=True)
    (app_root / "src" / "module.py").write_text("current src", encoding="utf-8")

    message = stage_restore_from_snapshot(snapshot, app_root=app_root)

    assert "run.bat" in message or "run.ps1" in message
    assert "update" in message.lower()
    staging = app_root / "update"
    assert staging.exists()
    assert (staging / "app.py").read_text(encoding="utf-8") == "from backup"
    assert (staging / "src" / "module.py").read_text(encoding="utf-8") == "from backup src"
    assert (app_root / "app.py").read_text(encoding="utf-8") == "current app"
    assert (app_root / "src" / "module.py").read_text(encoding="utf-8") == "current src"


def test_restore_backup_snapshot_copies_files_and_clears_pycache(tmp_path: Path) -> None:
    """Restoring a snapshot copies files back and clears __pycache__."""
    app_root = tmp_path
    snapshot = app_root / "backup" / "20260101-120000"
    snapshot.mkdir(parents=True)

    (snapshot / "app.py").write_text("from backup", encoding="utf-8")
    snapshot_src = snapshot / "src"
    snapshot_src.mkdir()
    (snapshot_src / "module.py").write_text("from backup src", encoding="utf-8")

    app_file = app_root / "app.py"
    app_file.write_text("current app", encoding="utf-8")
    src_dir = app_root / "src"
    src_dir.mkdir(exist_ok=True)
    src_file = src_dir / "module.py"
    src_file.write_text("current src", encoding="utf-8")

    pycache_dir = app_root / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "dummy.pyc").write_bytes(b"x")

    message = _restore_backup_snapshot(snapshot, app_root=app_root)
    assert "Backup restored" in message
    assert app_file.read_text(encoding="utf-8") == "from backup"
    assert src_file.read_text(encoding="utf-8") == "from backup src"
    assert not pycache_dir.exists()


def test_apply_staged_update_creates_backup_applies_and_returns_path(tmp_path: Path) -> None:
    """apply_staged_update creates backup, applies staged files, removes update/, returns path."""
    app_root = tmp_path
    app_file = app_root / "app.py"
    src_dir = app_root / "src"
    src_dir.mkdir()
    src_file = src_dir / "module.py"

    app_file.write_text("old app", encoding="utf-8")
    src_file.write_text("old src", encoding="utf-8")

    staging = app_root / "update"
    staging.mkdir()
    (staging / "app.py").write_text("new app", encoding="utf-8")
    (staging / "src").mkdir()
    (staging / "src" / "module.py").write_text("new src", encoding="utf-8")

    result = apply_staged_update(app_root=app_root)

    assert result is not None
    assert result.startswith("backup/")
    assert (app_root / result).exists()
    assert app_file.read_text(encoding="utf-8") == "new app"
    assert src_file.read_text(encoding="utf-8") == "new src"
    assert not staging.exists()

    backup_root = app_root / "backup"
    backups = [p for p in backup_root.iterdir() if p.is_dir()]
    assert len(backups) == 1
    snapshot = backups[0]
    assert (snapshot / "app.py").read_text(encoding="utf-8") == "old app"
    assert (snapshot / "src" / "module.py").read_text(encoding="utf-8") == "old src"

    sentinel = app_root / ".last_update_backup"
    assert sentinel.read_text(encoding="utf-8").strip() == result


def test_apply_staged_update_returns_none_when_no_update_dir(tmp_path: Path) -> None:
    """apply_staged_update returns None when update/ does not exist."""
    app_root = tmp_path
    assert apply_staged_update(app_root=app_root) is None


def test_apply_staged_update_returns_none_when_update_dir_empty(tmp_path: Path) -> None:
    """apply_staged_update returns None when update/ exists but has no files."""
    app_root = tmp_path
    (app_root / "update").mkdir()
    assert apply_staged_update(app_root=app_root) is None
