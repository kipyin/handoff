"""Additional tests for updater.py to improve edge case coverage."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from handoff.updater import (
    _backup_existing_files,
    _extract_zip_to_dir,
    _format_snapshot_label,
    _is_safe_member_path,
    _parse_version,
    _read_patch_members,
    _restore_backup_snapshot,
    apply_patch_zip,
    extract_patch_to_staging,
    get_patch_version,
    stage_patch_with_backup,
    stage_restore_from_snapshot,
)


def _make_zip(files: dict[str, bytes], version: str | None = None) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if version is not None:
            zf.writestr("VERSION", version)
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestGetPatchVersion:
    def test_returns_version_when_present(self) -> None:
        data = _make_zip({"app.py": b"x"}, version="2026.4.0")
        result = get_patch_version(BytesIO(data))
        assert result == "2026.4.0"

    def test_returns_none_when_no_version(self) -> None:
        data = _make_zip({"app.py": b"x"})
        result = get_patch_version(BytesIO(data))
        assert result is None


class TestParseVersion:
    def test_standard_version(self) -> None:
        assert _parse_version("2026.3.6") == (2026, 3, 6)

    def test_non_numeric_parts_become_zero(self) -> None:
        assert _parse_version("abc.def") == (0, 0)

    def test_single_part(self) -> None:
        assert _parse_version("42") == (42,)

    def test_whitespace_stripped(self) -> None:
        assert _parse_version("  2026.1.0  ") == (2026, 1, 0)


class TestIsSafeMemberPath:
    def test_valid_paths(self) -> None:
        assert _is_safe_member_path("src/module.py") is True
        assert _is_safe_member_path("app.py") is True
        assert _is_safe_member_path("src/sub/deep.py") is True

    def test_empty_path(self) -> None:
        assert _is_safe_member_path("") is False

    def test_absolute_paths(self) -> None:
        assert _is_safe_member_path("/etc/passwd") is False
        assert _is_safe_member_path("\\windows\\system32") is False

    def test_traversal(self) -> None:
        assert _is_safe_member_path("../escape") is False
        assert _is_safe_member_path("a/../../escape") is False


class TestReadPatchMembers:
    def test_skips_directories(self) -> None:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("src/", "")
            zf.writestr("src/module.py", b"code")
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            members, _ = _read_patch_members(zf)
        assert "src/" not in members
        assert "src/module.py" in members

    def test_release_notes_allowed(self) -> None:
        data = _make_zip({"RELEASE_NOTES.md": b"notes"})
        with zipfile.ZipFile(BytesIO(data)) as zf:
            members, _ = _read_patch_members(zf)
        assert "RELEASE_NOTES.md" in members


class TestExtractZipToDir:
    def test_extracts_files(self, tmp_path: Path) -> None:
        data = _make_zip({"src/module.py": b"code", "app.py": b"app"})
        with zipfile.ZipFile(BytesIO(data)) as zf:
            extracted, failed = _extract_zip_to_dir(zf, ["src/module.py", "app.py"], tmp_path)
        assert len(extracted) == 2
        assert len(failed) == 0
        assert (tmp_path / "src" / "module.py").read_bytes() == b"code"

    def test_reports_permission_error(self, tmp_path: Path, monkeypatch) -> None:
        data = _make_zip({"app.py": b"x"})
        original_open = Path.open

        def fail_open(self, *args, **kwargs):
            if self.name == "app.py" and "w" in str(args):
                raise PermissionError("locked")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr("pathlib.Path.open", fail_open)
        with zipfile.ZipFile(BytesIO(data)) as zf:
            _extracted, failed = _extract_zip_to_dir(zf, ["app.py"], tmp_path)
        assert "app.py" in failed


class TestBackupExistingFiles:
    def test_backs_up_existing_files(self, tmp_path: Path) -> None:
        app_root = tmp_path / "app"
        app_root.mkdir()
        backup_root = tmp_path / "backup"
        (app_root / "app.py").write_text("content")
        (app_root / "src").mkdir()
        (app_root / "src" / "mod.py").write_text("module")

        backed = _backup_existing_files(
            ["app.py", "src/mod.py", "missing.py"], app_root, backup_root
        )
        assert "app.py" in backed
        assert "src/mod.py" in backed
        assert "missing.py" not in backed
        assert (backup_root / "app.py").read_text() == "content"

    def test_handles_permission_error(self, tmp_path: Path, monkeypatch) -> None:
        app_root = tmp_path / "app"
        app_root.mkdir()
        backup_root = tmp_path / "backup"
        (app_root / "app.py").write_text("content")

        def fail_copy2(src, dst, **kw):
            raise PermissionError("nope")

        monkeypatch.setattr("shutil.copy2", fail_copy2)
        backed = _backup_existing_files(["app.py"], app_root, backup_root)
        assert backed == []


class TestStagePatchWithBackup:
    def test_no_applicable_files_message(self, tmp_path: Path) -> None:
        data = _make_zip({"ignored.txt": b"nope"})
        msg = stage_patch_with_backup(BytesIO(data), app_root=tmp_path, app_version="1.0.0")
        assert msg == "No applicable files found in patch zip."

    def test_without_version_in_zip(self, tmp_path: Path) -> None:
        data = _make_zip({"app.py": b"new"})
        msg = stage_patch_with_backup(BytesIO(data), app_root=tmp_path, app_version="1.0.0")
        assert "Update files are ready" in msg
        assert "handoff.bat" in msg


class TestExtractPatchToStaging:
    def test_extract_failed_message(self, tmp_path: Path, monkeypatch) -> None:
        """When all extractions fail, appropriate message is returned."""
        data = _make_zip({"app.py": b"x"})

        def fail_extract(zf, members, target_dir):
            return [], ["app.py"]

        monkeypatch.setattr("handoff.updater._extract_zip_to_dir", fail_extract)
        msg = extract_patch_to_staging(BytesIO(data), app_root=tmp_path)
        assert "Failed to extract" in msg

    def test_partial_extraction_warning(self, tmp_path: Path, monkeypatch) -> None:
        """When some files fail extraction, warning is appended."""
        data = _make_zip({"app.py": b"x", "src/a.py": b"y"})

        def partial_extract(zf, members, target_dir):
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "app.py").write_bytes(b"x")
            return ["app.py"], ["src/a.py"]

        monkeypatch.setattr("handoff.updater._extract_zip_to_dir", partial_extract)
        msg = extract_patch_to_staging(BytesIO(data), app_root=tmp_path)
        assert "Warning" in msg


class TestApplyPatchZip:
    def test_without_version_marker(self, tmp_path: Path, monkeypatch) -> None:
        logged: list[tuple[str, dict[str, str]]] = []
        monkeypatch.setattr(
            "handoff.updater._log_app_action",
            lambda action, **details: logged.append((action, details)),
        )
        data = _make_zip({"app.py": b"new app"})
        msg = apply_patch_zip(BytesIO(data), app_root=tmp_path)
        assert "Update applied" in msg
        assert (tmp_path / "app.py").read_bytes() == b"new app"
        assert logged == [("app_update", {})]


class TestFormatSnapshotLabel:
    def test_unrecognized_name_returned_as_is(self) -> None:
        p = Path("backup/not-a-timestamp")
        assert _format_snapshot_label(p) == "not-a-timestamp"

    def test_invalid_date_in_valid_format(self) -> None:
        p = Path("backup/99991399-999999")
        label = _format_snapshot_label(p)
        assert label == "99991399-999999"


class TestStageRestoreFromSnapshot:
    def test_missing_snapshot_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            stage_restore_from_snapshot(tmp_path / "nonexistent", app_root=tmp_path)

    def test_file_instead_of_dir_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "not_a_dir"
        f.write_text("x")
        with pytest.raises(FileNotFoundError):
            stage_restore_from_snapshot(f, app_root=tmp_path)


class TestRestoreBackupSnapshot:
    def test_missing_snapshot_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            _restore_backup_snapshot(tmp_path / "nonexistent", app_root=tmp_path)
