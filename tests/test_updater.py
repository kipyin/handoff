"""Tests for the in-app updater helpers."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from shutil import copy2 as real_copy2

from handoff.updater import (
    _backup_dir_name,
    _can_apply_patch,
    _clear_pycache,
    _format_snapshot_label,
    _is_safe_member_path,
    _iter_backup_snapshots,
    _read_patch_members,
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


def test_apply_patch_zip_applies_allowed_paths_and_creates_backup(
    tmp_path: Path, monkeypatch
) -> None:
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
    logged: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "handoff.updater._log_app_action",
        lambda action, **details: logged.append((action, details)),
    )

    message = apply_patch_zip(BytesIO(zip_bytes), app_root=app_root)
    assert "Target version: 2026.2.99" in message
    assert logged == [("app_update", {"target_version": "2026.2.99"})]

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


def test_log_app_action_delegates_to_bootstrap_logging(monkeypatch, tmp_path: Path) -> None:
    """_log_app_action delegates to bootstrap.logging.log_application_action."""
    from handoff.updater import _log_app_action

    fake_db_path = tmp_path / "handoff.db"
    logged: list[tuple[str, dict]] = []

    def mock_bootstrap_log(action: str, **details) -> None:
        logged.append((action, details))

    monkeypatch.setattr(
        "handoff.bootstrap.logging.log_application_action",
        mock_bootstrap_log,
    )
    # Mock get_db_path to return a platform-appropriate path
    monkeypatch.setattr(
        "handoff.db.get_db_path",
        lambda: fake_db_path,
    )

    _log_app_action("data_backup", size_mb=150)

    assert len(logged) == 1
    action, details = logged[0]
    assert action == "data_backup"
    assert details.get("db_path") == str(fake_db_path)
    assert details.get("size_mb") == 150


def test_log_app_action_handles_missing_db_path_gracefully(monkeypatch) -> None:
    """_log_app_action passes db_path=None when get_db_path() raises."""
    from handoff.updater import _log_app_action

    logged: list[tuple[str, dict]] = []

    def mock_bootstrap_log(action: str, **details) -> None:
        logged.append((action, details))

    monkeypatch.setattr(
        "handoff.bootstrap.logging.log_application_action",
        mock_bootstrap_log,
    )

    def raise_db_unavailable() -> None:
        raise RuntimeError("DB not available")

    monkeypatch.setattr("handoff.db.get_db_path", raise_db_unavailable)

    _log_app_action("app_update", target_version="2026.3.0")

    assert len(logged) == 1
    action, details = logged[0]
    assert action == "app_update"
    assert details.get("db_path") is None
    assert details.get("target_version") == "2026.3.0"


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
    assert "handoff.bat" in message
    # Staging dir contains new content.
    staging = app_root / "update"
    assert (staging / "app.py").read_text(encoding="utf-8") == "new app"
    assert (staging / "src" / "module.py").read_text(encoding="utf-8") == "new src"
    # App root is unchanged.
    assert app_file.read_text(encoding="utf-8") == "old app"


def test_extract_patch_to_staging_replaces_existing_staging_contents(tmp_path: Path) -> None:
    """Extracting a new patch should clear stale files from update/ first."""
    app_root = tmp_path
    stale_file = app_root / "update" / "src" / "stale.py"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale", encoding="utf-8")

    zip_bytes = _build_patch_zip_bytes({"app.py": b"new app"})
    extract_patch_to_staging(BytesIO(zip_bytes), app_root=app_root)

    assert (app_root / "update" / "app.py").read_text(encoding="utf-8") == "new app"
    assert not stale_file.exists()


def test_stage_patch_with_backup_creates_backup_and_staging_leaves_app_root_unchanged(
    tmp_path: Path,
    monkeypatch,
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
    logged: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "handoff.updater._log_app_action",
        lambda action, **details: logged.append((action, details)),
    )
    message = stage_patch_with_backup(
        BytesIO(zip_bytes),
        app_root=app_root,
        app_version="2026.3.1",
    )

    assert "2026.2.99" in message
    assert "handoff.bat" in message
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
    assert logged
    assert logged[0][0] == "app_backup"
    assert logged[0][1]["target_version"] == "2026.2.99"
    assert logged[0][1]["backup_path"].startswith(str(app_root / "backup"))


def test_stage_patch_with_backup_replaces_existing_staging_contents(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Staging a new patch should clear stale files from a previous staging run."""
    app_root = tmp_path
    stale_file = app_root / "update" / "src" / "stale.py"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale", encoding="utf-8")

    zip_bytes = _build_patch_zip_bytes({"app.py": b"fresh"})
    monkeypatch.setattr("handoff.updater._log_app_action", lambda *_a, **_k: None)

    stage_patch_with_backup(
        BytesIO(zip_bytes),
        app_root=app_root,
        app_version="2026.3.1",
    )

    assert (app_root / "update" / "app.py").read_text(encoding="utf-8") == "fresh"
    assert not stale_file.exists()


def test_extract_patch_to_staging_handles_staging_copy_failure_without_crash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A staging copy failure should return a clean error instead of raising."""
    app_root = tmp_path
    zip_bytes = _build_patch_zip_bytes({"app.py": b"new app"})

    def fail_copy2(_src, _dest, *_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("handoff.updater.shutil.copy2", fail_copy2)

    message = extract_patch_to_staging(BytesIO(zip_bytes), app_root=app_root)

    assert message == "Failed to extract patch to ./update."
    assert not (app_root / "update" / "app.py").exists()


def test_stage_patch_with_backup_handles_staging_copy_failure_without_crash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Patch staging failure should abort cleanly before backup/sentinel writes."""
    app_root = tmp_path
    (app_root / "app.py").write_text("old app", encoding="utf-8")
    zip_bytes = _build_patch_zip_bytes({"app.py": b"new app"})

    def fail_copy2(_src, _dest, *_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("handoff.updater.shutil.copy2", fail_copy2)

    message = stage_patch_with_backup(
        BytesIO(zip_bytes),
        app_root=app_root,
        app_version="2026.3.1",
    )

    assert message == "Failed to extract patch to ./update."
    assert not (app_root / "backup").exists()
    assert not (app_root / ".last_update_backup").exists()
    assert (app_root / "app.py").read_text(encoding="utf-8") == "old app"


def test_extract_patch_to_staging_partial_copy_failure_keeps_successful_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """One failed staged file should not crash or discard successfully staged files."""
    app_root = tmp_path
    zip_bytes = _build_patch_zip_bytes({"app.py": b"new app", "src/module.py": b"new src"})

    def fail_module_copy(src, dest, *_args, **_kwargs):
        if Path(src).name == "module.py":
            raise OSError("locked")
        return real_copy2(src, dest)

    monkeypatch.setattr("handoff.updater.shutil.copy2", fail_module_copy)

    message = extract_patch_to_staging(BytesIO(zip_bytes), app_root=app_root)

    assert message.startswith("Update files are ready.")
    assert "Warning: 1 file(s) could not be staged." in message
    assert (app_root / "update" / "app.py").read_text(encoding="utf-8") == "new app"
    assert not (app_root / "update" / "src" / "module.py").exists()


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
    monkeypatch,
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
    logged: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "handoff.updater._log_app_action",
        lambda action, **details: logged.append((action, details)),
    )

    message = stage_restore_from_snapshot(snapshot, app_root=app_root)

    assert "handoff.bat" in message
    assert "update" in message.lower()
    staging = app_root / "update"
    assert staging.exists()
    assert (staging / "app.py").read_text(encoding="utf-8") == "from backup"
    assert (staging / "src" / "module.py").read_text(encoding="utf-8") == "from backup src"
    assert (app_root / "app.py").read_text(encoding="utf-8") == "current app"
    assert (app_root / "src" / "module.py").read_text(encoding="utf-8") == "current src"
    assert logged == [
        ("app_restore", {"snapshot": str(snapshot), "staged": "true"}),
    ]


def test_restore_backup_snapshot_copies_files_and_clears_pycache(
    tmp_path: Path, monkeypatch
) -> None:
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
    logged: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "handoff.updater._log_app_action",
        lambda action, **details: logged.append((action, details)),
    )

    message = _restore_backup_snapshot(snapshot, app_root=app_root)
    assert "Backup restored" in message
    assert app_file.read_text(encoding="utf-8") == "from backup"
    assert src_file.read_text(encoding="utf-8") == "from backup src"
    assert not pycache_dir.exists()
    assert logged == [("app_restore", {"snapshot": str(snapshot), "applied": "true"})]


def test_apply_staged_update_creates_backup_applies_and_returns_path(
    tmp_path: Path, monkeypatch
) -> None:
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
    logged: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "handoff.updater._log_app_action",
        lambda action, **details: logged.append((action, details)),
    )

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
    assert logged == [("app_update", {"backup_path": result})]


def test_apply_staged_update_returns_none_when_no_update_dir(tmp_path: Path) -> None:
    """apply_staged_update returns None when update/ does not exist."""
    app_root = tmp_path
    assert apply_staged_update(app_root=app_root) is None


def test_apply_staged_update_returns_none_when_update_dir_empty(tmp_path: Path) -> None:
    """apply_staged_update returns None when update/ exists but has no files."""
    app_root = tmp_path
    (app_root / "update").mkdir()
    assert apply_staged_update(app_root=app_root) is None


def test_read_patch_members_includes_allowed_excludes_disallowed() -> None:
    """_read_patch_members returns only allowed paths; disallowed are skipped (warning logged)."""
    zip_bytes = _build_patch_zip_bytes(
        {"app.py": b"x", "src/foo.py": b"y", "other.txt": b"z", "README.md": b"readme"},
        version="2026.2.0",
    )
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        members, target_version = _read_patch_members(zf)
    assert target_version == "2026.2.0"
    assert "app.py" in members
    assert "src/foo.py" in members
    assert "README.md" in members
    assert "other.txt" not in members


def test_backup_dir_name_format() -> None:
    """_backup_dir_name returns timestamp-version<version> format."""
    result = _backup_dir_name("2026.3.6")
    assert result.endswith("-version2026.3.6")
    # Starts with YYYYMMDD-HHMMSS
    parts = result.rsplit("-", 1)
    assert len(parts) == 2
    date_part = parts[0]
    assert len(date_part) == 15  # YYYYMMDD-HHMMSS
    assert date_part[8] == "-"
    assert date_part[:8].isdigit()
    assert date_part[9:].isdigit()


def test_can_apply_patch_none_version_returns_true() -> None:
    """_can_apply_patch returns True when patch_version is None (no VERSION file)."""
    assert _can_apply_patch(None, "2026.3.6", False) is True


def test_can_apply_patch_newer_or_equal_returns_true() -> None:
    """_can_apply_patch returns True when patch version >= app version."""
    assert _can_apply_patch("2026.3.7", "2026.3.6", False) is True
    assert _can_apply_patch("2026.3.6", "2026.3.6", False) is True


def test_can_apply_patch_older_returns_false_unless_apply_anyway() -> None:
    """_can_apply_patch returns False when patch is older; True if apply_anyway."""
    assert _can_apply_patch("2026.3.5", "2026.3.6", False) is False
    assert _can_apply_patch("2026.3.5", "2026.3.6", True) is True


def test_can_apply_patch_invalid_version_parses_to_zeros() -> None:
    """_can_apply_patch treats non-numeric version as older.

    apply_anyway=True overrides the version check.
    """
    assert _can_apply_patch("not-a-version", "2026.3.6", False) is False
    assert _can_apply_patch("not-a-version", "2026.3.6", True) is True


# --- Zip Slip protection ---


def test_is_safe_member_path_rejects_traversal() -> None:
    """Paths with .. segments are rejected."""
    assert _is_safe_member_path("src/module.py") is True
    assert _is_safe_member_path("app.py") is True
    assert _is_safe_member_path("src/../etc/passwd") is False
    assert _is_safe_member_path("../outside.txt") is False
    assert _is_safe_member_path("") is False
    assert _is_safe_member_path("/absolute/path") is False


def test_read_patch_members_rejects_traversal_paths() -> None:
    """_read_patch_members skips entries containing .. segments."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", b"ok")
        zf.writestr("src/../etc/passwd", b"evil")
        zf.writestr("src/legit.py", b"ok too")
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        members, _ = _read_patch_members(zf)
    assert "app.py" in members
    assert "src/legit.py" in members
    assert "src/../etc/passwd" not in members


def test_apply_patch_zip_skips_traversal_paths(tmp_path: Path) -> None:
    """apply_patch_zip ignores zip entries with path traversal."""
    app_root = tmp_path
    (app_root / "app.py").write_text("old", encoding="utf-8")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", b"new")
        zf.writestr("src/../escape.txt", b"evil")
    buf.seek(0)

    apply_patch_zip(buf, app_root=app_root)
    assert (app_root / "app.py").read_text(encoding="utf-8") == "new"
    assert not (app_root / "escape.txt").exists()
    assert not (app_root.parent / "escape.txt").exists()
